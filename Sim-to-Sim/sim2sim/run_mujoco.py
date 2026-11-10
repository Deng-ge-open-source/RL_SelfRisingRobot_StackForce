from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_package_path(root: Path, value: str | None, label: str) -> Path:
    if not value:
        raise RuntimeError(f"The export manifest does not declare {label}.")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise RuntimeError(f"The declared {label} leaves the package: {value}") from error
    if not path.is_file():
        raise FileNotFoundError(f"The declared {label} is missing: {path}")
    return path


def load_model_with_ground(mujoco: Any, model_path: Path, runtime_dir: Path) -> tuple[Any, bool]:
    model = mujoco.MjModel.from_xml_path(str(model_path))
    has_plane = any(int(model.geom_type[index]) == int(mujoco.mjtGeom.mjGEOM_PLANE) for index in range(int(model.ngeom)))
    has_terrain = any(
        int(model.geom_type[index]) == int(mujoco.mjtGeom.mjGEOM_HFIELD)
        or (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, index) or "").startswith("__mjv_terrain_")
        for index in range(int(model.ngeom))
    )
    if has_plane or has_terrain:
        return model, False

    runtime_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = runtime_dir / "generated_ground_scene.xml"
    include_path = os.path.relpath(model_path, wrapper_path.parent).replace("\\", "/")
    escaped_include = include_path.replace("&", "&amp;").replace('"', "&quot;")
    wrapper_path.write_text(
        "\n".join(
            [
                '<mujoco model="StackForce local scene">',
                f'  <include file="{escaped_include}"/>',
                '  <worldbody>',
                '    <geom name="stackforce_ground" type="plane" size="0 0 0.1" rgba="0.72 0.76 0.80 1"/>',
                '  </worldbody>',
                '</mujoco>',
                '',
            ]
        ),
        encoding="utf-8",
    )
    return mujoco.MjModel.from_xml_path(str(wrapper_path)), True


def load_profile(root: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    module = manifest.get("module") or {}
    profile_value = module.get("sim2sim_profile")
    if not profile_value:
        return None
    return load_json(resolve_package_path(root, profile_value, "sim2sim profile"))


def load_declared_keyframe_qpos_lengths(model_path: Path) -> dict[str, int]:
    lengths: dict[str, int] = {}
    visited: set[Path] = set()

    def visit(xml_path: Path) -> None:
        resolved = xml_path.resolve()
        if resolved in visited or not resolved.is_file():
            return
        visited.add(resolved)
        try:
            root = ET.parse(resolved).getroot()
        except (OSError, ET.ParseError) as error:
            print(f"[StackForce] Could not inspect MJCF keyframes in {resolved}: {error}")
            return
        for include in root.findall(".//include"):
            include_value = include.get("file")
            if include_value:
                visit(resolved.parent / include_value.replace("\\", os.sep))
        for key in root.findall(".//keyframe/key"):
            name = key.get("name")
            qpos = key.get("qpos")
            if name and qpos is not None:
                lengths[name] = len(qpos.split())

    visit(model_path)
    return lengths


def repair_invalid_free_joint_poses(
    mujoco: Any,
    model: Any,
    data: Any,
    keyframe_id: int | None = None,
    declared_qpos_length: int | None = None,
) -> int:
    repaired = 0
    for joint_id in range(int(model.njnt)):
        if int(model.jnt_type[joint_id]) != int(mujoco.mjtJoint.mjJNT_FREE):
            continue
        qpos_id = int(model.jnt_qposadr[joint_id])
        data_pose = [float(data.qpos[qpos_id + offset]) for offset in range(7)]
        source_pose = data_pose
        if keyframe_id is not None and 0 <= keyframe_id < int(model.nkey):
            source_pose = [float(model.key_qpos[keyframe_id, qpos_id + offset]) for offset in range(7)]
        quat_norm_sq = sum(value * value for value in source_pose[3:7])
        pose_was_omitted = declared_qpos_length is not None and qpos_id + 7 > declared_qpos_length
        if not pose_was_omitted and all(math.isfinite(value) for value in source_pose) and quat_norm_sq > 1.0e-12:
            continue
        for offset in range(7):
            data.qpos[qpos_id + offset] = model.qpos0[qpos_id + offset]
        qvel_id = int(model.jnt_dofadr[joint_id])
        for offset in range(6):
            data.qvel[qvel_id + offset] = 0.0
        repaired += 1
    if repaired:
        mujoco.mj_normalizeQuat(model, data.qpos)
        print(f"[StackForce] Repaired {repaired} invalid free-joint poses from MJCF defaults.")
    return repaired


_FIXED_ROOT_OFFSET_DELTAS: dict[int, tuple[float, float, float]] = {}


def controlled_root_body_id(model: Any) -> int | None:
    """Return the top-level body that owns the largest controlled assembly."""
    controlled_root_scores: dict[int, int] = {}
    for actuator_id in range(int(model.nu)):
        actuator_joint_id = int(model.actuator_trnid[actuator_id, 0])
        if actuator_joint_id < 0 or actuator_joint_id >= int(model.njnt):
            continue
        body_id = int(model.jnt_bodyid[actuator_joint_id])
        while body_id > 0 and int(model.body_parentid[body_id]) > 0:
            body_id = int(model.body_parentid[body_id])
        if body_id > 0:
            controlled_root_scores[body_id] = controlled_root_scores.get(body_id, 0) + 1
    if not controlled_root_scores:
        return None
    return max(controlled_root_scores, key=controlled_root_scores.get)


def apply_configured_root_offset(
    mujoco: Any,
    model: Any,
    data: Any,
    profile: dict[str, Any] | None,
) -> bool:
    """Apply the exact root offset selected in the browser mapping page."""
    pose = ((profile or {}).get("runtime") or {}).get("pose") or {}
    raw_offset = pose.get("rootOffset")
    if not isinstance(raw_offset, list) or len(raw_offset) != 3:
        return False
    try:
        offset = [float(value) for value in raw_offset]
    except (TypeError, ValueError):
        return False
    root_z_mode = str(pose.get("rootZMode") or "offset")
    source_ground_z = float(pose.get("sourceGroundZ") or 0)
    fixed_base_ground_shift = (
        -source_ground_z
        if pose.get("groundPreset") == "robocon-arena" and math.isfinite(source_ground_z)
        else 0.0
    )
    if not all(math.isfinite(value) for value in offset):
        return False
    if root_z_mode != "absolute" and not any(abs(value) > 1.0e-12 for value in offset) and abs(fixed_base_ground_shift) <= 1.0e-12:
        return False

    best_root: tuple[int, int, int, list[int]] | None = None
    root_candidates: list[tuple[int, int, int, list[int]]] = []
    best_score = 0
    root_body_ids = {int(model.jnt_bodyid[joint_id]) for joint_id in range(int(model.njnt))}
    for root_body_id in root_body_ids:
        body_joint_ids = [
            joint_id
            for joint_id in range(int(model.njnt))
            if int(model.jnt_bodyid[joint_id]) == root_body_id
        ]
        free_joint_id = next(
            (
                joint_id
                for joint_id in body_joint_ids
                if int(model.jnt_type[joint_id]) == int(mujoco.mjtJoint.mjJNT_FREE)
            ),
            None,
        )
        root_candidate: tuple[int, int, int, list[int]] | None = None
        if free_joint_id is not None:
            qpos_id = int(model.jnt_qposadr[free_joint_id])
            qvel_id = int(model.jnt_dofadr[free_joint_id])
            root_candidate = (qpos_id, qpos_id + 1, qpos_id + 2, list(range(qvel_id, qvel_id + 6)))
        else:
            slide_qpos: dict[int, int] = {}
            slide_qvel: dict[int, int] = {}
            for joint_id in body_joint_ids:
                if int(model.jnt_type[joint_id]) != int(mujoco.mjtJoint.mjJNT_SLIDE):
                    continue
                axis = [abs(float(value)) for value in model.jnt_axis[joint_id]]
                primary_axis = max(range(3), key=lambda index: axis[index])
                if axis[primary_axis] <= 0.9 or sum(axis) - axis[primary_axis] >= 0.1:
                    continue
                slide_qpos[primary_axis] = int(model.jnt_qposadr[joint_id])
                slide_qvel[primary_axis] = int(model.jnt_dofadr[joint_id])
            if all(axis in slide_qpos for axis in (0, 1, 2)):
                root_dofs = [slide_qvel[axis] for axis in (0, 1, 2)]
                ball_joint_id = next(
                    (
                        joint_id
                        for joint_id in body_joint_ids
                        if int(model.jnt_type[joint_id]) == int(mujoco.mjtJoint.mjJNT_BALL)
                    ),
                    None,
                )
                if ball_joint_id is not None:
                    ball_dof_id = int(model.jnt_dofadr[ball_joint_id])
                    root_dofs.extend(range(ball_dof_id, ball_dof_id + 3))
                root_candidate = (slide_qpos[0], slide_qpos[1], slide_qpos[2], root_dofs)
        if root_candidate is None:
            continue
        root_candidates.append(root_candidate)
        score = 0
        for actuator_id in range(int(model.nu)):
            actuator_joint_id = int(model.actuator_trnid[actuator_id, 0])
            if actuator_joint_id < 0 or actuator_joint_id >= int(model.njnt):
                continue
            body_id = int(model.jnt_bodyid[actuator_joint_id])
            while body_id > 0 and body_id != root_body_id:
                body_id = int(model.body_parentid[body_id])
            if body_id == root_body_id:
                score += 1
        if score > best_score:
            best_root = root_candidate
            best_score = score
    if best_root is None:
        controlled_root_body = controlled_root_body_id(model)
        if controlled_root_body is None:
            return False
        model_identity = id(model)
        delta = _FIXED_ROOT_OFFSET_DELTAS.get(model_identity)
        if delta is None:
            delta = (
                offset[0] - float(model.body_pos[controlled_root_body, 0]),
                offset[1] - float(model.body_pos[controlled_root_body, 1]),
                offset[2] - float(model.body_pos[controlled_root_body, 2]) + fixed_base_ground_shift
                if root_z_mode == "absolute"
                else offset[2] + fixed_base_ground_shift,
            )
            model.body_pos[controlled_root_body, :3] += delta
            _FIXED_ROOT_OFFSET_DELTAS[model_identity] = delta

        # A fixed-base robot and its unconstrained task payloads share one
        # authored task space. Translate every free payload and mocap target by
        # the same delta while leaving welded/static terrain bodies untouched.
        for joint_id in range(int(model.njnt)):
            if int(model.jnt_type[joint_id]) != int(mujoco.mjtJoint.mjJNT_FREE):
                continue
            qpos_id = int(model.jnt_qposadr[joint_id])
            data.qpos[qpos_id : qpos_id + 3] += delta
            qvel_id = int(model.jnt_dofadr[joint_id])
            data.qvel[qvel_id : qvel_id + 6] = 0.0
        if int(model.nmocap) > 0:
            data.mocap_pos[:, :3] += delta

        print(
            "[StackForce] Applied browser root offset to fixed-base task space "
            f"({offset[0]:g}, {offset[1]:g}, {offset[2] + fixed_base_ground_shift:g})."
        )
        return True

    qpos_x, qpos_y, qpos_z, root_dof_ids = best_root
    data.qpos[qpos_x] = offset[0]
    data.qpos[qpos_y] = offset[1]
    if root_z_mode == "absolute":
        data.qpos[qpos_z] = offset[2]
    else:
        data.qpos[qpos_z] += offset[2]
    for qvel_id in root_dof_ids:
        data.qvel[qvel_id] = 0.0
    print(
        "[StackForce] Applied browser root offset "
        f"({offset[0]:g}, {offset[1]:g}, {offset[2]:g})."
    )
    return True


def has_distinct_reset_pose(mujoco: Any, model: Any, pose: dict[str, Any]) -> bool:
    reset_name, default_name = pose.get("resetKeyframe"), pose.get("defaultKeyframe")
    return bool(reset_name and default_name and reset_name != default_name
        and mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, str(reset_name)) >= 0
        and mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, str(default_name)) >= 0)


def apply_configured_joint_positions(
    mujoco: Any,
    model: Any,
    data: Any,
    profile: dict[str, Any] | None,
) -> int:
    pose = ((profile or {}).get("runtime") or {}).get("pose") or {}
    if has_distinct_reset_pose(mujoco, model, pose):
        return 0
    configured = pose.get("jointPositions") or {}
    if not isinstance(configured, dict):
        return 0
    applied = 0
    for raw_name, raw_value in configured.items():
        name = str(raw_name).strip()
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not name or not math.isfinite(value):
            continue
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            print(f"[StackForce] Ignoring q0 for missing joint: {name}")
            continue
        joint_type = int(model.jnt_type[joint_id])
        if joint_type not in (int(mujoco.mjtJoint.mjJNT_HINGE), int(mujoco.mjtJoint.mjJNT_SLIDE)):
            print(f"[StackForce] Ignoring scalar q0 for non-scalar joint: {name}")
            continue
        data.qpos[int(model.jnt_qposadr[joint_id])] = value
        data.qvel[int(model.jnt_dofadr[joint_id])] = 0.0
        applied += 1
    if applied:
        print(f"[StackForce] Applied {applied} configured policy-zero joint positions (q0).")
    return applied


def reset_model(
    mujoco: Any,
    model: Any,
    data: Any,
    profile: dict[str, Any] | None,
    keyframe_qpos_lengths: dict[str, int] | None = None,
) -> str | None:
    pose = ((profile or {}).get("runtime") or {}).get("pose") or {}
    candidates = [pose.get("resetKeyframe"), pose.get("defaultKeyframe"), "home", "stand", "default"]
    for candidate in candidates:
        if not candidate:
            continue
        key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, str(candidate))
        if key_id >= 0:
            mujoco.mj_resetDataKeyframe(model, data, key_id)
            declared_length = (keyframe_qpos_lengths or {}).get(str(candidate))
            repair_invalid_free_joint_poses(mujoco, model, data, key_id, declared_length)
            apply_configured_root_offset(mujoco, model, data, profile)
            apply_configured_joint_positions(mujoco, model, data, profile)
            mujoco.mj_forward(model, data)
            return str(candidate)
    if model.nkey > 0:
        mujoco.mj_resetDataKeyframe(model, data, 0)
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_KEY, 0)
        declared_length = (keyframe_qpos_lengths or {}).get(str(name)) if name else None
        repair_invalid_free_joint_poses(mujoco, model, data, 0, declared_length)
        apply_configured_root_offset(mujoco, model, data, profile)
        apply_configured_joint_positions(mujoco, model, data, profile)
        mujoco.mj_forward(model, data)
        return str(name or "#0")
    mujoco.mj_resetData(model, data)
    apply_configured_root_offset(mujoco, model, data, profile)
    apply_configured_joint_positions(mujoco, model, data, profile)
    mujoco.mj_forward(model, data)
    return None


def validate_policy(root: Path, manifest: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
    policy_info = manifest.get("policy") or {}
    policy_value = policy_info.get("path")
    if not policy_value:
        return {"status": "not_present"}
    policy_path = resolve_package_path(root, policy_value, "ONNX policy")
    try:
        import onnxruntime as ort
    except ImportError as error:
        raise RuntimeError(
            "ONNX Runtime is required to validate the exported policy. "
            "Install sim2sim/requirements.txt first."
        ) from error

    session = ort.InferenceSession(str(policy_path), providers=["CPUExecutionProvider"])
    inputs = [{"name": item.name, "shape": list(item.shape), "type": item.type} for item in session.get_inputs()]
    outputs = [{"name": item.name, "shape": list(item.shape), "type": item.type} for item in session.get_outputs()]
    expected_obs = int(policy_info.get("obs_dim") or ((profile or {}).get("policy") or {}).get("observationDim") or 0)
    expected_action = int(policy_info.get("action_dim") or ((profile or {}).get("policy") or {}).get("actionDim") or 0)

    def trailing_dim(items: list[dict[str, Any]]) -> int | None:
        if not items or not items[0]["shape"]:
            return None
        value = items[0]["shape"][-1]
        return int(value) if isinstance(value, int) else None

    actual_obs = trailing_dim(inputs)
    actual_action = trailing_dim(outputs)
    if expected_obs and actual_obs and expected_obs != actual_obs:
        raise RuntimeError(f"ONNX observation dimension mismatch: profile={expected_obs}, model={actual_obs}")
    if expected_action and actual_action and expected_action != actual_action:
        raise RuntimeError(f"ONNX action dimension mismatch: profile={expected_action}, model={actual_action}")
    return {
        "status": "configuration_validated",
        "path": str(policy_path.relative_to(root)),
        "inputs": inputs,
        "outputs": outputs,
        "note": "The ONNX session and profile dimensions are valid. The interactive viewer executes supported profile-driven policy control by default.",
    }


def robot_camera_body_ids(model: Any) -> list[int]:
    actuator_bodies: list[int] = []
    for actuator_id in range(int(model.nu)):
        joint_id = int(model.actuator_trnid[actuator_id, 0])
        if 0 <= joint_id < int(model.njnt):
            actuator_bodies.append(int(model.jnt_bodyid[joint_id]))

    def ancestors(body_id: int) -> list[int]:
        result = [body_id]
        while result[-1] > 0:
            result.append(int(model.body_parentid[result[-1]]))
        result.reverse()
        return result

    robot_root = 0
    if actuator_bodies:
        chains = [ancestors(body_id) for body_id in actuator_bodies]
        for candidates in zip(*chains):
            if len(set(candidates)) != 1:
                break
            robot_root = int(candidates[0])

    body_ids: list[int] = []
    for body_id in range(1, int(model.nbody)):
        cursor = body_id
        while cursor > 0 and cursor != robot_root:
            cursor = int(model.body_parentid[cursor])
        if robot_root > 0 and cursor == robot_root:
            body_ids.append(body_id)
    if not body_ids:
        body_ids = sorted(set(actuator_bodies)) or list(range(1, int(model.nbody)))
    return body_ids


def robot_camera_pose(model: Any, data: Any, body_ids: list[int] | None = None) -> tuple[Any, float]:
    import numpy as np

    if body_ids is None:
        body_ids = robot_camera_body_ids(model)
    points = np.asarray(data.xpos[body_ids], dtype=np.float64)
    if points.size == 0:
        center = np.asarray(data.qpos[:3] if model.nq >= 3 else [0, 0, 0.5], dtype=np.float64)
        return center, max(float(model.stat.extent) * 2.25, 1.25)
    minimum = points.min(axis=0)
    maximum = points.max(axis=0)
    center = (minimum + maximum) * 0.5
    span = float(np.max(maximum - minimum))
    return center, max(span * 2.4, 0.8)


MAX_SIMULATION_BACKLOG_SECONDS = 0.25
MAX_SIMULATION_STEPS_PER_TICK = 512
VIEWER_RENDER_INTERVAL_SECONDS = 1.0 / 60.0


def realtime_step_budget(accumulator: float, elapsed: float, timestep: float) -> tuple[float, int]:
    safe_timestep = max(float(timestep), 1.0e-6)
    safe_accumulator = max(0.0, float(accumulator)) if math.isfinite(accumulator) else 0.0
    safe_elapsed = max(0.0, float(elapsed)) if math.isfinite(elapsed) else 0.0
    available = min(MAX_SIMULATION_BACKLOG_SECONDS, safe_accumulator + safe_elapsed)
    steps = min(MAX_SIMULATION_STEPS_PER_TICK, int((available + 1.0e-12) / safe_timestep))
    return max(0.0, available - steps * safe_timestep), steps


def render_frame(mujoco: Any, model: Any, data: Any, destination: Path, width: int, height: int) -> None:
    import numpy as np

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exported scenes often keep MuJoCo's 640x480 offscreen default. Grow the
    # runtime framebuffer without rewriting the user's MJCF.
    model.vis.global_.offwidth = max(int(model.vis.global_.offwidth), width)
    model.vis.global_.offheight = max(int(model.vis.global_.offheight), height)
    renderer = mujoco.Renderer(model, height=height, width=width)
    try:
        camera = mujoco.MjvCamera()
        mujoco.mjv_defaultCamera(camera)
        camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        lookat, distance = robot_camera_pose(model, data)
        camera.distance = distance
        camera.azimuth = 135
        camera.elevation = -18
        camera.lookat[:] = lookat
        renderer.update_scene(data, camera=camera)
        image = renderer.render()
        try:
            from PIL import Image
        except ImportError as error:
            raise RuntimeError("Pillow is required only when --render is used.") from error
        Image.fromarray(image).save(destination)
    finally:
        renderer.close()


def sensor_values(mujoco: Any, model: Any, data: Any, name: str) -> Any:
    import numpy as np

    sensor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, name)
    if sensor_id < 0:
        raise RuntimeError(f"The runtime profile requires missing sensor: {name}")
    start = int(model.sensor_adr[sensor_id])
    dim = int(model.sensor_dim[sensor_id])
    return np.asarray(data.sensordata[start:start + dim], dtype=np.float32)


def parse_scale(transform: Any) -> float:
    value = str(transform or "")
    if value.startswith("scale:"):
        return float(value.split(":", 1)[1])
    return 1.0


def parse_number_list(value: Any) -> list[float]:
    if isinstance(value, (int, float)):
        return [float(value)]
    if not isinstance(value, str):
        return []
    result: list[float] = []
    for part in value.replace(",", " ").split():
        try:
            result.append(float(part))
        except ValueError:
            continue
    return result


def repeated(values: Any, dim: int, np: Any) -> Any:
    source = np.asarray(values, dtype=np.float32).reshape(-1)
    if dim <= 0:
        return np.zeros(0, dtype=np.float32)
    if source.size == 0:
        return np.zeros(dim, dtype=np.float32)
    return np.resize(source, dim).astype(np.float32, copy=False)


def manual_group_leaf_index(group: dict[str, Any]) -> int | None:
    label = str(group.get("label") or "")
    identifier = str(group.get("id") or "")
    text = f"{identifier} {label}"
    matches = re.findall(r"(?:cmd|joint|action|phase|item)(\d+)", text, flags=re.IGNORECASE)
    if matches:
        return int(matches[-1])
    suffix = label.rsplit(":", 1)[-1].strip().lower()
    return {
        "wx": 0,
        "wy": 1,
        "wz": 2,
        "ax": 0,
        "ay": 1,
        "az": 2,
        "vx": 0,
        "vy": 1,
        "vz": 2,
        "qw": 0,
        "qx": 1,
        "qy": 2,
        "qz": 3,
        "roll": 0,
        "pitch": 1,
        "yaw": 2,
    }.get(suffix)


def observation_source_component_index(source_id: str, labels: list[str] | tuple[str, ...] = ()) -> int | None:
    suffix = str(source_id or "").rsplit(":", 1)[-1].strip()
    for index, label in enumerate(labels):
        if str(label).lower() == suffix.lower():
            return index
    numeric = re.search(r"(?:item|cmd|contact|action|joint|phase|policy)(\d+)$", suffix, flags=re.IGNORECASE)
    if numeric:
        return max(0, int(numeric.group(1)))
    return {
        "wx": 0,
        "wy": 1,
        "wz": 2,
        "ax": 0,
        "ay": 1,
        "az": 2,
        "vx": 0,
        "vy": 1,
        "vz": 2,
        "x": 0,
        "y": 1,
        "z": 2,
        "qw": 0,
        "qx": 1,
        "qy": 2,
        "qz": 3,
        "roll": 0,
        "pitch": 1,
        "yaw": 2,
        "cosl": 0,
        "cosr": 1,
        "sinl": 2,
        "sinr": 3,
    }.get(suffix.lower())


def manual_group_values(values: Any, group: dict[str, Any], dim: int, np: Any) -> Any:
    source = np.asarray(values, dtype=np.float32).reshape(-1)
    leaf_index = manual_group_leaf_index(group)
    if bool(group.get("manual")) and dim == 1 and leaf_index is not None and leaf_index < source.size:
        return source[leaf_index:leaf_index + 1]
    return repeated(source, dim, np)


def apply_transform(values: Any, transform: Any, np: Any) -> Any:
    result = np.asarray(values, dtype=np.float32).copy()
    for operation in str(transform or "").replace("|", ";").split(";"):
        name, separator, raw_value = operation.strip().partition(":")
        if not separator:
            continue
        if name == "scale_vector":
            scales = np.asarray(
                [float(item) for item in re.split(r"[,\s]+", raw_value.strip()) if item],
                dtype=np.float32,
            )
            if scales.size:
                result *= np.resize(scales, result.size)
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        if name == "scale":
            result *= value
        elif name in {"bias_first", "add_first"} and result.size:
            result[0] += value
        elif name == "zero_first":
            result[:max(0, int(value))] = 0
    return result


def frame_span_start(span: Any) -> int:
    value = str(span or "")
    if "[" not in value or ":" not in value:
        return 0
    try:
        return max(0, int(value.split("[", 1)[1].split(":", 1)[0]))
    except ValueError:
        return 0


def quat_to_euler(quaternion: Any, np: Any) -> Any:
    values = np.asarray(quaternion, dtype=np.float64).reshape(-1)
    w, x, y, z = (list(values[:4]) + [1.0, 0.0, 0.0, 0.0])[:4]
    roll = np.arctan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch = np.arcsin(np.clip(2.0 * (w * y - z * x), -1.0, 1.0))
    yaw = np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return np.asarray([roll, pitch, yaw], dtype=np.float32)


def quat_multiply(left: Any, right: Any, np: Any) -> Any:
    lw, lx, ly, lz = np.asarray(left, dtype=np.float64).reshape(-1)[:4]
    rw, rx, ry, rz = np.asarray(right, dtype=np.float64).reshape(-1)[:4]
    return np.asarray([
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ], dtype=np.float64)


def quat_to_matrix(quaternion: Any, np: Any) -> Any:
    w, x, y, z = np.asarray(quaternion, dtype=np.float64).reshape(-1)[:4]
    norm = max(float(np.sqrt(w * w + x * x + y * y + z * z)), 1.0e-12)
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    return np.asarray([
        1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y),
        2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x),
        2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y),
    ], dtype=np.float64).reshape(3, 3)


def resolve_profile_action_actuators(mujoco: Any, model: Any, action: dict[str, Any]) -> list[tuple[dict[str, Any], str, int]]:
    action_groups = sorted(list(action.get("groups") or []), key=lambda item: int(item.get("index") or 0))
    joint_assignments = action.get("jointAssignments") or {}
    if not isinstance(joint_assignments, dict):
        joint_assignments = {}
    actuator_names = [
        str(mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index) or "")
        for index in range(int(model.nu))
    ]
    groups_by_id = {
        str(group.get("id") or ""): group
        for group in action_groups
        if str(group.get("id") or "")
    }
    resolved: list[tuple[dict[str, Any], str, int]] = []
    owners: dict[int, str] = {}

    for index, group in enumerate(action_groups):
        group_id = str(group.get("id") or f"action-{index}")
        assigned_id = str(joint_assignments.get(group_id) or "").strip()
        actuator_name = ""
        assigned_group = groups_by_id.get(assigned_id)
        if assigned_group is not None:
            actuator_name = str(assigned_group.get("target") or assigned_group.get("actuator") or "")
        elif assigned_id in actuator_names:
            actuator_name = assigned_id
        elif assigned_id:
            indexed_target = re.match(r"^(?:actuator|motor|joint|ctrl)(?:[-:\s]|\[)*(\d+)\]?$", assigned_id, re.IGNORECASE)
            if indexed_target is not None:
                assigned_index = int(indexed_target.group(1))
                if 0 <= assigned_index < len(actuator_names):
                    actuator_name = actuator_names[assigned_index]
            if not actuator_name:
                prefixed_name = re.sub(r"^(?:actuator|motor|joint|ctrl):", "", assigned_id, flags=re.IGNORECASE)
                if prefixed_name in actuator_names:
                    actuator_name = prefixed_name
                else:
                    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, prefixed_name)
                    if joint_id >= 0:
                        for actuator_index in range(int(model.nu)):
                            if int(model.actuator_trnid[actuator_index, 0]) == int(joint_id):
                                actuator_name = actuator_names[actuator_index]
                                break
        if not actuator_name:
            actuator_name = str(group.get("actuator") or group.get("target") or "")
        actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
        if actuator_id < 0:
            assignment_note = f" (assignment {assigned_id})" if assigned_id else ""
            raise RuntimeError(f"Action {group_id} requires missing actuator: {actuator_name}{assignment_note}")
        previous_owner = owners.get(int(actuator_id))
        if previous_owner is not None:
            raise RuntimeError(f"Action mappings {previous_owner} and {group_id} share actuator {actuator_name}.")
        owners[int(actuator_id)] = group_id
        resolved.append((group, actuator_name, int(actuator_id)))
    return resolved


class ProfilePolicyController:
    def __init__(
        self,
        mujoco: Any,
        model: Any,
        data: Any,
        root: Path,
        manifest: dict[str, Any],
        profile: dict[str, Any],
        command_vx: float | None,
    ) -> None:
        import numpy as np
        import onnxruntime as ort

        self.mujoco = mujoco
        self.model = model
        self.data = data
        self.profile = profile
        self.np = np
        runtime = profile.get("runtime") or {}
        self.family = str(runtime.get("family") or "")
        self.project_id = str(runtime.get("projectId") or "")
        raw_root_offset = ((runtime.get("pose") or {}).get("rootOffset") or [0, 0, 0])
        self.root_offset = np.asarray(
            raw_root_offset if isinstance(raw_root_offset, list) and len(raw_root_offset) == 3 else [0, 0, 0],
            dtype=np.float64,
        )
        policy_info = manifest.get("policy") or {}
        policy_path = resolve_package_path(root, policy_info.get("path"), "ONNX policy")
        self.session = ort.InferenceSession(str(policy_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [item.name for item in self.session.get_outputs()]
        action_output_name = str((profile.get("action") or {}).get("outputName") or "")
        self.output_name = action_output_name if action_output_name in self.output_names else self.output_names[0]
        observation = profile.get("observation") or {}
        self.groups = list(observation.get("groups") or [])
        raw_observation_assignments = observation.get("assignments") or {}
        self.observation_assignments = (
            {
                str(target_id): str(source_id)
                for target_id, source_id in raw_observation_assignments.items()
                if source_id
            }
            if isinstance(raw_observation_assignments, dict)
            else {}
        )
        self.frame_stack = observation.get("frameStack") or None
        self.frame_history: list[Any] = []
        self.obs_dim = int((profile.get("policy") or {}).get("observationDim") or 0)
        self.action_dim = int((profile.get("policy") or {}).get("actionDim") or model.nu)
        timing = runtime.get("timing") or {}
        sim_dt = float(timing.get("simDt") or 0.0)
        if sim_dt > 0:
            self.model.opt.timestep = sim_dt
        self.decimation = max(1, int(timing.get("decimation") or round(float(timing.get("controlDt") or 0.02) / float(model.opt.timestep))))
        command = runtime.get("command") or {}
        defaults = list(command.get("defaults") or [])
        components = [str(item) for item in list(command.get("components") or [])]
        self.command = np.asarray(defaults, dtype=np.float32)
        self.command_components = components
        self.command_limits = list(command.get("limits") or [])
        self.command_control = command.get("control") or {}
        adapters = ((runtime.get("adapters") or {}).get("adapters") or [])
        self.adapters = list(adapters)
        command_adapter = next((item for item in adapters if item.get("type") == "command" and item.get("enabled")), None)
        self.command_adapter_params = (command_adapter or {}).get("params") or {}
        self.command_deadzone = max(0.0, float(self.command_adapter_params.get("deadzone") or 0.01))
        self.idle_gait_frequency = max(0.0, float(self.command_adapter_params.get("idleGaitFrequency") or 0.0))
        self.active_gait_frequency = max(0.0, float(self.command_adapter_params.get("activeGaitFrequency") or 3.0))
        self.idle_clock_mode = str(self.command_adapter_params.get("idleClockMode") or "freeze")
        self.idle_action_mode = str(self.command_adapter_params.get("idleActionMode") or "policy")
        self.idle_policy_seconds = max(0.0, float(self.command_adapter_params.get("idlePolicySeconds") or 0.4))
        self.idle_action_fade_seconds = max(0.0, float(self.command_adapter_params.get("idleActionFadeSeconds") or 0.8))
        self.idle_action_transition_start_step = -1
        self.remote_control_enabled = bool(command.get("enabled")) and bool(
            self.command_control.get("exposeToControl", True)
        )
        signs = self.command_control.get("axisSigns") or {}
        self.remote_axis_signs = {
            "vx": -1.0 if float(signs.get("vx") or 1) < 0 else 1.0,
            "vy": -1.0 if float(signs.get("vy") or 1) < 0 else 1.0,
            "yaw": -1.0 if float(signs.get("yaw") or 1) < 0 else 1.0,
        }
        presets = self.command_control.get("presets") or {}
        self.remote_walk_preset = list(presets.get("walk") or [])
        self.remote_stop_preset = list(presets.get("stop") or [])
        self.remote_initial = list(self.command_control.get("initial") or [])
        self.remote_axes = {"vx": 0.0, "vy": 0.0, "yaw": 0.0}
        for axis in ("vx", "vy", "yaw"):
            index = self._command_axis_index(axis)
            if index is not None and index < self.command.size:
                fallback = float(self.command[index]) * self.remote_axis_signs[axis]
                self.set_remote_axis(axis, self._remote_preset_value(axis, self.remote_initial, fallback), clamp_to_active_range=False)
        if command_vx is not None:
            self.set_remote_axis("vx", float(command_vx))

        action = profile.get("action") or {}
        action_groups = sorted(list(action.get("groups") or []), key=lambda item: int(item.get("index") or 0))
        self.action_groups = action_groups
        resolved_action_actuators = resolve_profile_action_actuators(mujoco, model, action)
        control = action.get("control") or {}
        self.actuator_ids: list[int] = []
        self.joint_ids: list[int] = []
        self.scales: list[float] = []
        self.offsets: list[float] = []
        self.signs: list[float] = []
        self.limits: list[float] = []
        self.modes: list[str] = []
        self.kps: list[float] = []
        self.kds: list[float] = []
        self.actuator_dynamics: list[dict[str, Any]] = []
        for index, (group, actuator_name, actuator_id) in enumerate(resolved_action_actuators):
            joint_id = int(model.actuator_trnid[actuator_id, 0])
            params = control.get(str(group.get("id") or f"action-{index}")) or {}
            self.actuator_ids.append(actuator_id)
            self.joint_ids.append(joint_id)
            self.scales.append(float(params.get("scale") if params.get("scale") is not None else 1.0))
            self.offsets.append(float(params.get("offset") or 0.0))
            self.signs.append(float(params.get("sign") if params.get("sign") is not None else 1.0))
            self.limits.append(float(params.get("limit") if params.get("limit") is not None else float("inf")))
            self.modes.append(str(params.get("mode") or "position"))
            self.kps.append(float(params.get("kp") if params.get("kp") is not None else 40.0))
            self.kds.append(float(params.get("kd") if params.get("kd") is not None else 1.2))
            dynamics = params.get("actuatorDynamics") or {}
            self.actuator_dynamics.append(dynamics)
            if dynamics.get("type") == "dc_position":
                # Same stateless voltage drive as the browser. Back-EMF stays
                # in MuJoCo's implicit integrator; limits come from the profile.
                resistance = float(dynamics["resistance"])
                motor = float(dynamics["motorConstant"])
                voltage = float(dynamics["voltageLimit"])
                effort = float(dynamics["effortLimit"])
                model.actuator_gaintype[actuator_id] = mujoco.mjtGain.mjGAIN_FIXED
                model.actuator_biastype[actuator_id] = mujoco.mjtBias.mjBIAS_AFFINE
                model.actuator_gainprm[actuator_id, 0] = motor / resistance
                model.actuator_biasprm[actuator_id, :3] = [0, 0, -motor*motor/resistance]
                model.actuator_ctrllimited[actuator_id] = model.actuator_forcelimited[actuator_id] = True
                model.actuator_ctrlrange[actuator_id] = [-voltage, voltage]
                model.actuator_forcerange[actuator_id] = [-effort, effort]

        configured_joint_positions = (runtime.get("pose") or {}).get("jointPositions") or {}
        default_key_name = str((runtime.get("pose") or {}).get("defaultKeyframe") or "")
        default_key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, default_key_name) if default_key_name else -1
        distinct_reset_pose = has_distinct_reset_pose(mujoco, model, runtime.get("pose") or {})
        default_targets: list[float] = []
        configured_target_mask: list[bool] = []
        for index, joint_id in enumerate(self.joint_ids):
            joint_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id) or ""
            configured_value = configured_joint_positions.get(joint_name) if isinstance(configured_joint_positions, dict) else None
            try:
                configured_float = float(configured_value)
            except (TypeError, ValueError):
                configured_float = float("nan")
            qpos_id = int(model.jnt_qposadr[joint_id])
            if math.isfinite(configured_float):
                if not distinct_reset_pose:
                    data.qpos[qpos_id] = configured_float
                    data.qvel[int(model.jnt_dofadr[joint_id])] = 0.0
                default_targets.append(configured_float)
                configured_target_mask.append(True)
            else:
                default_targets.append(float(model.key_qpos[default_key_id, qpos_id]) if default_key_id >= 0 else float(data.qpos[qpos_id]))
                configured_target_mask.append(False)
        self.default_targets = np.asarray(default_targets, dtype=np.float32)
        self.configured_target_mask = np.asarray(configured_target_mask, dtype=np.bool_)
        self.motor_targets = self.default_targets.copy()
        self.previous_motor_targets = self.default_targets.copy()
        self.last_action = np.zeros(self.action_dim, dtype=np.float32)
        self.action_history: list[Any] = [np.zeros(self.action_dim, dtype=np.float32) for _ in range(3)]
        self.policy_step = 0
        self.legacy_angular_velocity_sensor_reads = 0
        self.first_observation: Any | None = None
        self.first_action: Any | None = None
        self.signal_history_states: dict[str, dict[str, Any]] = {}

        actuator_adapter = next((item for item in adapters if item.get("type") == "actuator_net" and item.get("enabled")), None)
        self.actuator_params = (actuator_adapter or {}).get("params") or {}
        self.actuator_session = None
        self.actuator_input_name = ""
        self.actuator_output_name = ""
        self.actuator_default_joint_pos = np.zeros(self.action_dim, dtype=np.float32)
        self.actuator_policy_default_joint_pos = np.zeros(self.action_dim, dtype=np.float32)
        self.policy_to_model_order = list(range(self.action_dim))
        self.model_to_policy_order = list(range(self.action_dim))
        self.actuator_action_scale = 1.0
        self.actuator_policy_joint_velocity_scale = 1.0
        self.actuator_hip_scale = 1.0
        self.actuator_hip_indices: set[int] = set()
        self.actuator_torque_limit = float("inf")
        self.actuator_lag: list[Any] = []
        self.actuator_joint_error = [np.zeros(self.action_dim, dtype=np.float32) for _ in range(2)]
        self.actuator_joint_velocity = [np.zeros(self.action_dim, dtype=np.float32) for _ in range(2)]
        if self.actuator_params:
            actuator_url = str(self.actuator_params.get("url") or "")
            actuator_filename = Path(actuator_url.replace("\\", "/")).name
            actuator_path = resolve_package_path(root, f"module/policy/{actuator_filename}", "actuator ONNX model")
            self.actuator_session = ort.InferenceSession(str(actuator_path), providers=["CPUExecutionProvider"])
            actuator_inputs = [item.name for item in self.actuator_session.get_inputs()]
            actuator_outputs = [item.name for item in self.actuator_session.get_outputs()]
            requested_input = str(self.actuator_params.get("inputName") or "")
            requested_output = str(self.actuator_params.get("outputName") or "")
            self.actuator_input_name = requested_input if requested_input in actuator_inputs else actuator_inputs[0]
            self.actuator_output_name = requested_output if requested_output in actuator_outputs else actuator_outputs[0]
            adapter_default_joint_pos = repeated(parse_number_list(self.actuator_params.get("defaultJointPos")), self.action_dim, np)
            self.actuator_default_joint_pos = np.where(
                self.configured_target_mask,
                self.default_targets,
                adapter_default_joint_pos,
            ).astype(np.float32)
            self.actuator_policy_default_joint_pos = repeated(parse_number_list(self.actuator_params.get("policyDefaultJointPos")), self.action_dim, np)
            policy_to_model = [int(value) for value in parse_number_list(self.actuator_params.get("policyToModelOrder"))]
            model_to_policy = [int(value) for value in parse_number_list(self.actuator_params.get("modelToPolicyOrder"))]
            if len(policy_to_model) == self.action_dim:
                self.policy_to_model_order = policy_to_model
            if len(model_to_policy) == self.action_dim:
                self.model_to_policy_order = model_to_policy
            self.actuator_action_scale = float(self.actuator_params.get("actionScale") or 1.0)
            self.actuator_policy_joint_velocity_scale = float(self.actuator_params.get("policyJointVelocityScale") or 1.0)
            self.actuator_hip_scale = float(self.actuator_params.get("hipScaleReduction") or 1.0)
            self.actuator_hip_indices = {int(value) for value in parse_number_list(self.actuator_params.get("hipIndices"))}
            self.actuator_torque_limit = float(self.actuator_params.get("torqueLimit") or float("inf"))
            lag_steps = max(0, int(self.actuator_params.get("lagSteps") or 0))
            self.actuator_lag = [np.zeros(self.action_dim, dtype=np.float32) for _ in range(lag_steps + 1)]
            self.default_targets = self.actuator_default_joint_pos.copy()
            self.motor_targets = self.default_targets.copy()
            self.previous_motor_targets = self.default_targets.copy()
            for index, joint_id in enumerate(self.joint_ids):
                self.data.qpos[int(self.model.jnt_qposadr[joint_id])] = self.actuator_default_joint_pos[index]
                self.data.qvel[int(self.model.jnt_dofadr[joint_id])] = 0
                self.data.ctrl[self.actuator_ids[index]] = 0
            initial_root_height = float(self.actuator_params.get("initialRootHeight") or 0)
            if initial_root_height > 0 and self.model.nq >= 7:
                self.data.qpos[2] = initial_root_height + float(self.root_offset[2])
                self.data.qpos[3:7] = [1, 0, 0, 0]
                self.data.qvel[:6] = 0
            self.mujoco.mj_forward(self.model, self.data)

        motor_adapter = next((item for item in adapters if item.get("type") == "motor_target_cache" and item.get("enabled")), None)
        motor_params = (motor_adapter or {}).get("params") or {}
        self.max_motor_velocity = float(motor_params.get("maxVelocity") or 0.0)
        phase_adapter = next((item for item in adapters if item.get("type") == "phase_clock" and item.get("enabled")), None)
        phase_params = (phase_adapter or {}).get("params") or {}
        self.phase_period = max(1.0, float(phase_params.get("period") or 1.0))
        self.phase_format = str(phase_params.get("format") or "cos_sin")
        self.phase_clock_mode = str(phase_params.get("clockMode") or "fixed_period_steps")
        self.phase_reference_linear_speed = max(1.0e-6, abs(float(phase_params.get("referenceLinearSpeed") or 1.0)))
        self.phase_reference_yaw_speed = max(1.0e-6, abs(float(phase_params.get("referenceYawSpeed") or 1.0)))
        self.phase_translation_frequency_scale = max(1.0e-6, float(phase_params.get("translationFrequencyScale") or 1.0))
        self.phase_yaw_frequency_scale = max(1.0e-6, float(phase_params.get("yawFrequencyScale") or 1.0))
        self.phase_minimum_period_seconds = max(1.0e-6, float(phase_params.get("minimumPeriodSeconds") or 0.5))
        self.phase_maximum_period_seconds = max(
            self.phase_minimum_period_seconds,
            float(phase_params.get("maximumPeriodSeconds") or 1.0),
        )
        self.phase_base_frequency_hz = max(0.0, float(phase_params.get("baseFrequencyHz") or 1.25))
        self.phase_frequency_gain_hz_per_command = float(phase_params.get("frequencyGainHzPerCommand") or (1.0 / 3.0))
        self.phase_maximum_command_magnitude = max(0.0, float(phase_params.get("maximumCommandMagnitude") or 1.5))
        self.phase_idle_command_threshold = max(0.0, float(phase_params.get("idleCommandThreshold") or 0.0001))
        self.phase_angle = 0.0
        self.phase_stop_after_cycles = max(0.0, float(phase_params.get("stopAfterCycles") or 0.0))
        self.phase_initial = float(phase_params.get("initialPhase") or 0.0)
        self.phase_update = str(phase_params.get("update") or "policy_step")
        self.phase_offset = self.np.pi
        self.gait_index = 0.0
        self.motor_initial_delay = max(0, int(motor_params.get("initialDelaySteps") or 0))
        self.incremental_motor_targets = any(
            any(token in f"{group.get('mode') or ''} {group.get('scale') or ''} {group.get('source') or ''}".lower() for token in ("incremental", "+=", "last target", "previous target"))
            for group in self.action_groups
        )
        motor_scale = parse_number_list(motor_params.get("actionScale"))
        self.motor_scales = repeated(motor_scale or self.scales or [1.0], self.action_dim, self.np)

        reference_adapter = next((item for item in adapters if item.get("type") == "reference_motion" and item.get("enabled")), None)
        self.reference_params = (reference_adapter or {}).get("params") or {}
        self.reference_joint_pos = np.zeros(self.action_dim, dtype=np.float32)
        self.reference_joint_vel = np.zeros(self.action_dim, dtype=np.float32)
        self.reference_body_quat = np.zeros(0, dtype=np.float32)
        self.reference_ready = False
        self.reference_time_step = 0
        self.reference_max_time_step = max(1, int(self.reference_params.get("maxTimeStep") or 1))
        self.reference_body_names = [item.strip() for item in str(self.reference_params.get("bodyNames") or "").split(",") if item.strip()]
        self.reference_anchor_name = str(self.reference_params.get("anchorBody") or "")
        self.reference_anchor_body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, self.reference_anchor_name) if self.reference_anchor_name else -1
        self.reference_yaw_align = np.eye(3, dtype=np.float64)
        reference_defaults = parse_number_list(self.reference_params.get("defaultJointPos"))
        if reference_defaults:
            adapter_reference_defaults = repeated(reference_defaults, len(self.actuator_ids), self.np)
            self.default_targets = self.np.where(
                self.configured_target_mask,
                self.default_targets,
                adapter_reference_defaults,
            ).astype(self.np.float32)
            self.motor_targets = self.default_targets.copy()
            self.previous_motor_targets = self.default_targets.copy()
            for index, actuator_id in enumerate(self.actuator_ids):
                qpos_id = int(self.model.jnt_qposadr[self.joint_ids[index]])
                self.data.qpos[qpos_id] = self.default_targets[index]
                self.data.ctrl[actuator_id] = self.default_targets[index]
            self.mujoco.mj_forward(self.model, self.data)
        if self.reference_params:
            self.bootstrap_reference_state()

        virtual_servo_adapter = next((item for item in adapters if item.get("type") == "virtual_servo_state" and item.get("enabled")), None)
        self.virtual_servo_params = (virtual_servo_adapter or {}).get("params") or {}
        joint_damping = float(self.virtual_servo_params.get("jointDamping") or 0)
        joint_armature = float(self.virtual_servo_params.get("jointArmature") or 0)
        for joint_id in self.joint_ids:
            dof_id = int(self.model.jnt_dofadr[joint_id])
            if joint_damping > 0:
                self.model.dof_damping[dof_id] = joint_damping
            if joint_armature > 0:
                self.model.dof_armature[dof_id] = joint_armature
        reset_to_policy_zero = str(self.virtual_servo_params.get("resetPosition") or "policy_zero") == "policy_zero"
        self.virtual_servo_position = self.default_targets.copy() if reset_to_policy_zero else np.zeros(self.action_dim, dtype=np.float32)
        self.virtual_servo_velocity = np.zeros(self.action_dim, dtype=np.float32)
        self.virtual_servo_target = self.virtual_servo_position.copy()
        self.virtual_servo_lower = np.full(self.action_dim, -float("inf"), dtype=np.float32)
        self.virtual_servo_upper = np.full(self.action_dim, float("inf"), dtype=np.float32)
        for index, joint_id in enumerate(self.joint_ids):
            if bool(self.model.jnt_limited[joint_id]):
                self.virtual_servo_lower[index] = float(self.model.jnt_range[joint_id, 0])
                self.virtual_servo_upper[index] = float(self.model.jnt_range[joint_id, 1])

    def _command_axis_index(self, axis: str) -> int | None:
        aliases = {
            "vx": ("vx", "linear_x", "forward_velocity", "forward"),
            "vy": ("vy", "linear_y", "lateral_velocity", "strafe"),
            "yaw": ("yaw", "yaw_rate", "angular_z", "turn"),
        }
        normalized = [
            re.sub(r"[^a-z0-9]+", "_", item.strip().lower()).strip("_")
            for item in self.command_components
        ]
        for alias in aliases.get(axis, (axis,)):
            if alias in normalized:
                return normalized.index(alias)
        fallback = {"vx": 0, "vy": 1, "yaw": 2}.get(axis)
        return fallback if fallback is not None and fallback < self.command.size else None

    def _policy_axis_range(self, axis: str) -> tuple[float, float]:
        index = self._command_axis_index(axis)
        if index is not None and index < len(self.command_limits):
            value = self.command_limits[index]
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                low, high = float(value[0]), float(value[1])
                return min(low, high), max(low, high)
        fallbacks = {"vx": (-0.3, 0.8), "vy": (-0.3, 0.3), "yaw": (-0.8, 0.8)}
        return fallbacks.get(axis, (-1.0, 1.0))

    def remote_axis_range(self, axis: str) -> tuple[float, float]:
        low, high = self._policy_axis_range(axis)
        sign = self.remote_axis_signs.get(axis, 1.0)
        values = sorted((low * sign, high * sign))
        return float(values[0]), float(values[1])

    def _remote_preset_value(self, axis: str, preset: list[Any], fallback: float = 0.0) -> float:
        index = {"vx": 0, "vy": 1, "yaw": 2}.get(axis, -1)
        if index >= 0 and index < len(preset):
            try:
                return float(preset[index])
            except (TypeError, ValueError):
                pass
        return fallback

    def remote_value_from_intent(self, axis: str, intent: float) -> float:
        low, high = self.remote_axis_range(axis)
        directed = max(-1.0, min(1.0, float(intent)))
        preset = self._remote_preset_value(axis, self.remote_walk_preset, 0.0)
        if abs(preset) > 0:
            directional_limit = max(0.0, high) if directed >= 0 else abs(min(0.0, low))
            return directed * min(abs(preset), directional_limit)
        return directed * max(0.0, high) if directed >= 0 else -directed * min(0.0, low)

    def set_remote_axis(self, axis: str, value: float, clamp_to_active_range: bool = True) -> bool:
        index = self._command_axis_index(axis)
        if index is None or index >= self.command.size:
            return False
        was_idle = self.command_is_idle()
        low, high = self.remote_axis_range(axis)
        semantic_value = max(low, min(high, float(value))) if clamp_to_active_range else float(value)
        policy_low, policy_high = self._policy_axis_range(axis)
        policy_value = semantic_value * self.remote_axis_signs.get(axis, 1.0)
        self.command[index] = max(policy_low, min(policy_high, policy_value)) if clamp_to_active_range else policy_value
        self.remote_axes[axis] = semantic_value
        is_idle = self.command_is_idle()
        if not was_idle and is_idle:
            self.idle_action_transition_start_step = int(getattr(self, "policy_step", 0))
        elif was_idle and not is_idle:
            self.idle_action_transition_start_step = -1
        return True

    def command_is_idle(self) -> bool:
        magnitude = math.sqrt(sum(float(value) * float(value) for value in self.command[:3]))
        return magnitude < float(getattr(self, "command_deadzone", 0.01))

    def idle_action_scale(self) -> float:
        if not self.command_is_idle():
            return 1.0
        if self.idle_action_mode == "zero":
            return 0.0
        if self.idle_action_mode != "settle_then_zero":
            return 1.0
        if self.idle_action_transition_start_step < 0:
            return 0.0
        elapsed = max(0, self.policy_step - self.idle_action_transition_start_step) * float(self.model.opt.timestep) * self.decimation
        if elapsed <= self.idle_policy_seconds:
            return 1.0
        if self.idle_action_fade_seconds <= 1.0e-6:
            return 0.0
        progress = max(0.0, min(1.0, (elapsed - self.idle_policy_seconds) / self.idle_action_fade_seconds))
        smooth = progress * progress * (3.0 - 2.0 * progress)
        return 1.0 - smooth

    def stop_remote_control(self) -> None:
        for axis in ("vx", "vy", "yaw"):
            self.set_remote_axis(axis, self._remote_preset_value(axis, self.remote_stop_preset, 0.0))

    def remote_status(self) -> str:
        return "vx={vx:.3f}, vy={vy:.3f}, yaw={yaw:.3f}".format(**self.remote_axes)

    def handle_remote_key(self, keycode: int) -> None:
        if not self.remote_control_enabled:
            return
        bindings = {
            265: ("vx", 1.0), 87: ("vx", 1.0), 119: ("vx", 1.0),
            264: ("vx", -1.0), 83: ("vx", -1.0), 115: ("vx", -1.0),
            263: ("yaw", 1.0), 65: ("yaw", 1.0), 97: ("yaw", 1.0),
            262: ("yaw", -1.0), 68: ("yaw", -1.0), 100: ("yaw", -1.0),
            81: ("vy", 1.0), 113: ("vy", 1.0),
            69: ("vy", -1.0), 101: ("vy", -1.0),
        }
        if keycode == 32:
            self.stop_remote_control()
        elif keycode in bindings:
            axis, intent = bindings[keycode]
            self.set_remote_axis(axis, self.remote_value_from_intent(axis, intent))
        else:
            return
        print(f"[StackForce] Remote command / 当前遥控指令: {self.remote_status()}")

    def print_remote_control_help(self) -> None:
        if not self.remote_control_enabled:
            print("[StackForce] Remote control is disabled by this profile / 当前工程未启用遥控。")
            return
        ranges = ", ".join(
            f"{axis}=[{self.remote_axis_range(axis)[0]:g}, {self.remote_axis_range(axis)[1]:g}]"
            for axis in ("vx", "vy", "yaw")
            if self._command_axis_index(axis) is not None
        )
        signs = ", ".join(f"{axis}={self.remote_axis_signs[axis]:+g}" for axis in ("vx", "vy", "yaw"))
        walk = [self._remote_preset_value(axis, self.remote_walk_preset, 0.0) for axis in ("vx", "vy", "yaw")]
        print("[StackForce] Keyboard remote control inherited from sim2sim.profile.json.")
        print("[StackForce] 键盘遥控已继承网页工程中的 sim2sim.profile.json 设置。")
        print("[StackForce] UP/W forward, DOWN/S backward, LEFT/A turn left, RIGHT/D turn right, Q/E strafe, SPACE stop.")
        print("[StackForce] 上/W 前进，下/S 后退，左/A 左转，右/D 右转，Q/E 横移，空格停止。")
        print(f"[StackForce] Inherited limits / 继承范围: {ranges}")
        print(f"[StackForce] Walk preset / 行走预设: {walk}; axis signs / 方向符号: {signs}")
        print(f"[StackForce] Initial command / 初始指令: {self.remote_status()}")

    def joint_id_for_name(self, name: str) -> int:
        joint_id = self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id >= 0:
            return int(joint_id)
        actuator_id = self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_ACTUATOR, name)
        if actuator_id >= 0:
            return int(self.model.actuator_trnid[actuator_id, 0])
        return -1

    def joint_position(self, joint_name: str) -> float:
        joint_id = self.joint_id_for_name(joint_name)
        if joint_id < 0:
            raise RuntimeError(f"The runtime profile requires missing joint: {joint_name}")
        qpos_id = int(self.model.jnt_qposadr[joint_id])
        default = 0.0
        if joint_id in self.joint_ids:
            default = float(self.default_targets[self.joint_ids.index(joint_id)])
        return float(self.data.qpos[qpos_id]) - default

    def joint_velocity(self, joint_name: str) -> float:
        joint_id = self.joint_id_for_name(joint_name)
        if joint_id < 0:
            raise RuntimeError(f"The runtime profile requires missing joint: {joint_name}")
        return float(self.data.qvel[int(self.model.jnt_dofadr[joint_id])])

    def contacts(self, targets: list[str], dim: int) -> Any:
        floor_name = targets[0] if targets else "floor"
        foot_names = targets[1:] if len(targets) > 1 else []
        floor_id = self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_GEOM, floor_name)
        foot_ids = [self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_GEOM, name) for name in foot_names]
        values = self.np.zeros(dim, dtype=self.np.float32)
        for contact_index in range(int(self.data.ncon)):
            contact = self.data.contact[contact_index]
            pair = {int(contact.geom1), int(contact.geom2)}
            for index, foot_id in enumerate(foot_ids[:dim]):
                if floor_id in pair and foot_id in pair:
                    values[index] = 1.0
        return values

    def automatic_floor_geom_ids(self, excluded_ids: set[int]) -> set[int]:
        named_ground_ids: list[int] = []
        world_ground_ids: list[int] = []
        for geom_id in range(int(self.model.ngeom)):
            if geom_id in excluded_ids:
                continue
            contact_enabled = int(self.model.geom_contype[geom_id]) != 0 or int(self.model.geom_conaffinity[geom_id]) != 0
            if not contact_enabled:
                continue
            name = self.mujoco.mj_id2name(self.model, self.mujoco.mjtObj.mjOBJ_GEOM, geom_id) or ""
            if re.search(r"floor|ground|terrain|hfield|plane", name, re.IGNORECASE):
                named_ground_ids.append(geom_id)
            if int(self.model.geom_bodyid[geom_id]) == 0:
                world_ground_ids.append(geom_id)
        return set(named_ground_ids or world_ground_ids)

    def foot_contacts(self, foot_names: list[str], dim: int) -> Any:
        foot_ids = [
            self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_GEOM, name)
            for name in foot_names
        ]
        floor_ids = self.automatic_floor_geom_ids({item for item in foot_ids if item >= 0})
        values = self.np.zeros(dim, dtype=self.np.float32)
        for contact_index in range(int(self.data.ncon)):
            contact = self.data.contact[contact_index]
            geom1 = int(contact.geom1)
            geom2 = int(contact.geom2)
            for index, foot_id in enumerate(foot_ids[:dim]):
                if foot_id < 0 or (geom1 != foot_id and geom2 != foot_id):
                    continue
                other_geom = geom2 if geom1 == foot_id else geom1
                if not floor_ids or other_geom in floor_ids:
                    values[index] = 1.0
        return values

    def sensor_or_none(self, names: list[str]) -> Any | None:
        for name in names:
            sensor_id = self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_SENSOR, name)
            if sensor_id >= 0:
                start = int(self.model.sensor_adr[sensor_id])
                dim = int(self.model.sensor_dim[sensor_id])
                return self.np.asarray(self.data.sensordata[start:start + dim], dtype=self.np.float32)
        return None

    def gravity_values(self, targets: list[str]) -> Any:
        site_names = [*targets, "imu", "imu_in_pelvis"]
        for name in site_names:
            site_id = self.mujoco.mj_name2id(self.model, self.mujoco.mjtObj.mjOBJ_SITE, name)
            if site_id >= 0:
                matrix = self.np.asarray(self.data.site_xmat[site_id], dtype=self.np.float32).reshape(3, 3)
                return self.np.asarray([-matrix[2, 0], -matrix[2, 1], -matrix[2, 2]], dtype=self.np.float32)
        return self.np.asarray([0.0, 0.0, -1.0], dtype=self.np.float32)

    def base_euler(self, targets: list[str]) -> Any:
        quaternion = self.sensor_or_none([*targets, "orientation"])
        if quaternion is None or quaternion.size < 4:
            quaternion = self.np.asarray(self.data.qpos[3:7], dtype=self.np.float32)
        return quat_to_euler(quaternion, self.np)

    def leap_position_error(self) -> Any:
        palm = self.sensor_or_none(["palm_position"])
        cube = self.sensor_or_none(["cube_position"])
        return repeated((palm if palm is not None else [0, 0, 0]), 3, self.np) - repeated((cube if cube is not None else [0, 0, 0]), 3, self.np)

    def leap_orientation_error(self) -> Any:
        cube = self.sensor_or_none(["cube_orientation"])
        goal = self.sensor_or_none(["cube_goal_orientation"])
        if cube is None or cube.size < 4 or goal is None or goal.size < 4:
            return self.np.zeros(6, dtype=self.np.float32)
        relative = quat_multiply(cube[:4], [goal[0], -goal[1], -goal[2], -goal[3]], self.np)
        matrix = quat_to_matrix(relative, self.np).reshape(-1)
        return self.np.asarray(matrix[3:9], dtype=self.np.float32)

    def quaternion_yaw(self, quaternion: Any) -> float:
        values = self.np.asarray(quaternion, dtype=self.np.float64).reshape(-1)
        w, x, y, z = (list(values[:4]) + [1.0, 0.0, 0.0, 0.0])[:4]
        return float(self.np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))

    def update_reference_outputs(self, outputs: dict[str, Any]) -> None:
        joint_pos = outputs.get(str(self.reference_params.get("jointPosOutput") or "joint_pos"))
        joint_vel = outputs.get(str(self.reference_params.get("jointVelOutput") or "joint_vel"))
        body_quat = outputs.get(str(self.reference_params.get("bodyQuatOutput") or "body_quat_w"))
        if joint_pos is None or joint_vel is None or body_quat is None:
            raise RuntimeError("Reference-motion ONNX output is missing joint or body state tensors.")
        was_ready = self.reference_ready
        self.reference_joint_pos = repeated(joint_pos, self.action_dim, self.np)
        self.reference_joint_vel = repeated(joint_vel, self.action_dim, self.np)
        self.reference_body_quat = self.np.asarray(body_quat, dtype=self.np.float32).reshape(-1)
        self.reference_ready = True
        if not was_ready and self.reference_anchor_body_id >= 0 and self.reference_anchor_name in self.reference_body_names:
            anchor_index = self.reference_body_names.index(self.reference_anchor_name)
            reference_quat = self.reference_body_quat[anchor_index * 4:anchor_index * 4 + 4]
            current_quat = self.np.asarray(self.data.xquat[self.reference_anchor_body_id], dtype=self.np.float64)
            delta_yaw = self.quaternion_yaw(current_quat) - self.quaternion_yaw(reference_quat)
            cosine = float(self.np.cos(delta_yaw))
            sine = float(self.np.sin(delta_yaw))
            self.reference_yaw_align = self.np.asarray(
                [[cosine, -sine, 0], [sine, cosine, 0], [0, 0, 1]],
                dtype=self.np.float64,
            )

    def bootstrap_reference_state(self) -> None:
        feeds = {self.input_name: self.np.zeros((1, self.obs_dim), dtype=self.np.float32)}
        for item in self.session.get_inputs()[1:]:
            if item.name == str(self.reference_params.get("timestepSource") or "time_step") or item.name == "time_step":
                feeds[item.name] = self.np.zeros((1, 1), dtype=self.np.float32)
        results = self.session.run(self.output_names, feeds)
        outputs = dict(zip(self.output_names, results))
        joint_pos = outputs.get(str(self.reference_params.get("jointPosOutput") or "joint_pos"))
        joint_vel = outputs.get(str(self.reference_params.get("jointVelOutput") or "joint_vel"))
        body_pos = outputs.get(str(self.reference_params.get("bodyPosOutput") or "body_pos_w"))
        body_quat = outputs.get(str(self.reference_params.get("bodyQuatOutput") or "body_quat_w"))
        body_lin_vel = outputs.get(str(self.reference_params.get("bodyLinVelOutput") or "body_lin_vel_w"))
        body_ang_vel = outputs.get(str(self.reference_params.get("bodyAngVelOutput") or "body_ang_vel_w"))
        required = [joint_pos, joint_vel, body_pos, body_quat, body_lin_vel, body_ang_vel]
        if any(value is None for value in required):
            raise RuntimeError("Reference-motion ONNX output cannot bootstrap the initial MuJoCo state.")
        joint_pos_values = repeated(joint_pos, self.action_dim, self.np)
        joint_vel_values = repeated(joint_vel, self.action_dim, self.np)
        root_pos = self.np.asarray(body_pos, dtype=self.np.float32).reshape(-1, 3)[0]
        root_quat = self.np.asarray(body_quat, dtype=self.np.float32).reshape(-1, 4)[0]
        root_lin_vel = self.np.asarray(body_lin_vel, dtype=self.np.float32).reshape(-1, 3)[0]
        root_ang_vel = self.np.asarray(body_ang_vel, dtype=self.np.float32).reshape(-1, 3)[0]
        if self.model.nq >= 7:
            self.data.qpos[:3] = root_pos + self.root_offset
            self.data.qpos[3:7] = root_quat
            self.data.qvel[:3] = root_lin_vel
            self.data.qvel[3:6] = root_ang_vel
        for index, joint_id in enumerate(self.joint_ids):
            self.data.qpos[int(self.model.jnt_qposadr[joint_id])] = joint_pos_values[index]
            self.data.qvel[int(self.model.jnt_dofadr[joint_id])] = joint_vel_values[index]
            self.data.ctrl[self.actuator_ids[index]] = joint_pos_values[index]
        self.mujoco.mj_forward(self.model, self.data)
        self.update_reference_outputs(outputs)
        self.reference_time_step = 0

    def reference_anchor_orientation(self) -> Any:
        if not self.reference_ready or self.reference_anchor_body_id < 0 or self.reference_anchor_name not in self.reference_body_names:
            return self.np.asarray([1, 0, 0, 1, 0, 0], dtype=self.np.float32)
        anchor_index = self.reference_body_names.index(self.reference_anchor_name)
        reference_quat = self.reference_body_quat[anchor_index * 4:anchor_index * 4 + 4]
        current_quat = self.np.asarray(self.data.xquat[self.reference_anchor_body_id], dtype=self.np.float64)
        current_rotation = quat_to_matrix(current_quat, self.np)
        reference_rotation = quat_to_matrix(reference_quat, self.np)
        local_rotation = current_rotation.T @ self.reference_yaw_align @ reference_rotation
        return self.np.asarray(
            [local_rotation[0, 0], local_rotation[0, 1], local_rotation[1, 0], local_rotation[1, 1], local_rotation[2, 0], local_rotation[2, 1]],
            dtype=self.np.float32,
        )

    def phase_values(self, dim: int) -> Any:
        angle = (
            self.phase_angle
            if self.phase_clock_mode in {"command_conditioned_period", "command_magnitude_frequency"}
            else (self.policy_step % self.phase_period) / self.phase_period * 2.0 * self.np.pi
        )
        if self.phase_stop_after_cycles > 0 and self.phase_clock_mode == "fixed_period_steps":
            step = self.policy_step * (self.decimation if self.phase_update == "simulation_step" else 1)
            if self.phase_update == "before_inference":
                step += 1
            angle = self.phase_initial + min(self.phase_stop_after_cycles, step / self.phase_period) * 2 * self.np.pi
        phases = [angle, angle + self.phase_offset]
        if self.phase_format == "sin_cos":
            values = [self.np.sin(phases[0]), self.np.cos(phases[0])]
        elif self.phase_format == "sin_cos_4":
            values = [self.np.sin(phases[0]), self.np.sin(phases[1]), self.np.cos(phases[0]), self.np.cos(phases[1])]
        elif self.phase_format in {"gait_sin_4", "sin_4"}:
            command = self.command.copy()
            moving = self.np.linalg.norm(command[:3]) >= 0.01 if command.size >= 3 else False
            if command.size >= 5:
                command[4] = self.active_gait_frequency if moving else self.idle_gait_frequency
            frequency = float(command[4]) if command.size >= 5 else 1.0
            if abs(frequency) < 1.0e-6 and self.idle_clock_mode == "zero":
                self.gait_index = 0.0
                return self.np.zeros(dim, dtype=self.np.float32)
            phase = float(command[5]) if command.size >= 6 else 0.5
            offset = float(command[6]) if command.size >= 7 else 0.0
            bound = float(command[7]) if command.size >= 8 else 0.0
            duration = min(0.95, max(0.05, float(command[8]) if command.size >= 9 else 0.5))
            foot_phases = [self.gait_index + phase + offset + bound, self.gait_index + offset, self.gait_index + bound, self.gait_index + phase]
            def warped(value: float) -> float:
                value %= 1.0
                return value * (0.5 / duration) if value < duration else 0.5 + (value - duration) * (0.5 / (1.0 - duration))
            values = [self.np.sin(2.0 * self.np.pi * warped(item)) for item in foot_phases]
            self.gait_index = (self.gait_index + float(self.model.opt.timestep) * self.decimation * frequency) % 1.0
        elif self.phase_format == "cos_sin":
            values = [self.np.cos(phases[0]), self.np.sin(phases[0])]
        else:
            values = [self.np.cos(phases[0]), self.np.cos(phases[1]), self.np.sin(phases[0]), self.np.sin(phases[1])]
        return repeated(values, dim, self.np)

    def advance_command_conditioned_phase(self) -> None:
        if self.phase_clock_mode not in {"command_conditioned_period", "command_magnitude_frequency"}:
            return
        command = repeated(self.command, 3, self.np)
        vx, vy, yaw = (float(command[index]) for index in range(3))
        threshold = self.phase_idle_command_threshold
        control_dt = float(self.model.opt.timestep) * self.decimation
        if self.phase_clock_mode == "command_magnitude_frequency":
            magnitude = float(self.np.linalg.norm(command[:3]))
            active_magnitude = 0.0 if magnitude < threshold else min(magnitude, self.phase_maximum_command_magnitude)
            frequency = max(0.0, self.phase_base_frequency_hz + self.phase_frequency_gain_hz_per_command * active_magnitude)
            self.phase_angle = (self.phase_angle + 2.0 * self.np.pi * control_dt * frequency) % (2.0 * self.np.pi)
            return
        if abs(vx) <= threshold and abs(vy) <= threshold and abs(yaw) <= threshold:
            self.phase_angle = 0.0
            return
        translation_score = self.np.hypot(vx, vy) / self.phase_reference_linear_speed
        yaw_score = abs(yaw) / self.phase_reference_yaw_speed
        frequency_scale = (
            self.phase_translation_frequency_scale
            if translation_score >= yaw_score
            else self.phase_yaw_frequency_scale
        )
        speed_factor = min(1.0, max(0.0, float(translation_score)))
        period = self.phase_maximum_period_seconds - (
            self.phase_maximum_period_seconds - self.phase_minimum_period_seconds
        ) * speed_factor
        self.phase_angle = (
            self.phase_angle + 2.0 * self.np.pi * control_dt * frequency_scale / period
        ) % (2.0 * self.np.pi)

    def command_values(self, dim: int) -> Any:
        values = repeated(self.command, dim, self.np)
        if "walk_these_ways" in self.family or self.project_id == "walk-these-ways-go1":
            moving = self.np.linalg.norm(values[:3]) >= 0.01 if values.size >= 3 else False
            if values.size >= 5:
                values[4] = self.active_gait_frequency if moving else self.idle_gait_frequency
            scales = [2.0, 2.0, 0.25, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.15, 0.3, 0.3, 1.0, 1.0, 1.0]
            values *= repeated(scales, dim, self.np)
        return values

    def constant_assignment_values(self, source_id: str, dim: int) -> Any | None:
        sequence_prefix = "runtime:command_sequence"
        if source_id == sequence_prefix or source_id.startswith(sequence_prefix + ":"):
            adapter = next((a for a in self.adapters if a.get("type") == "command_sequence" and a.get("enabled")), None)
            if adapter is None:
                raise ValueError("Command sequence requires an enabled adapter")
            params = adapter.get("params") or {}
            frames = json.loads(str(params.get("keyframes") or "[]"))
            dimension = int(params.get("dim") or 0)
            previous_time = -1
            if not frames or dimension < 1:
                raise ValueError("Invalid command sequence dimension/keyframes")
            for i, frame in enumerate(frames):
                t, v = frame["time"], frame["values"]
                if not self.np.isfinite(t) or t <= previous_time or (i == 0 and t != 0) or len(v) != dimension or not self.np.isfinite(v).all():
                    raise ValueError("Invalid command sequence keyframe")
                previous_time = t
            time = self.policy_step * float(self.model.opt.timestep) * self.decimation
            if params.get("playback") == "loop" and frames[-1]["time"] > 0:
                time %= frames[-1]["time"]
            index = 0
            while index + 1 < len(frames) and time + 1e-9 >= frames[index + 1]["time"]:
                index += 1
            current = frames[index]
            values = self.np.array(current["values"], dtype=self.np.float32)
            if params.get("interpolation") == "linear" and index + 1 < len(frames):
                following = frames[index + 1]
                weight = min(1.0, max(0.0, (time - current["time"]) / (following["time"] - current["time"])))
                values += (self.np.array(following["values"], dtype=self.np.float32) - values) * weight
            match = re.search(r":item(\d+)$", source_id)
            return self.assignment_scalar(values, int(match.group(1)), dim) if match else repeated(values, dim, self.np)
        prefix = "runtime:constant_zero"
        if source_id != prefix and not source_id.startswith(f"{prefix}:"):
            return None
        adapter = next(
            (
                item
                for item in self.adapters
                if item.get("type") == "constant_zero" and item.get("enabled")
            ),
            None,
        )
        if adapter is None:
            return None
        params = adapter.get("params") or {}
        configured = parse_number_list(params.get("value")) or [0.0]
        return self.np.full(max(0, int(dim)), float(configured[0]), dtype=self.np.float32)

    def assignment_scalar(self, values: Any, index: int | None, dim: int) -> Any:
        source = self.np.asarray(values, dtype=self.np.float32).reshape(-1)
        resolved_index = max(0, int(index or 0))
        if resolved_index >= source.size:
            return self.np.zeros(dim, dtype=self.np.float32)
        return repeated(source[resolved_index:resolved_index + 1], dim, self.np)

    def assignment_vector(
        self,
        source_id: str,
        prefix: str,
        values: Any,
        dim: int,
        labels: list[str] | tuple[str, ...] = (),
    ) -> Any | None:
        if source_id == prefix:
            return repeated(values, dim, self.np)
        if not source_id.startswith(f"{prefix}:"):
            return None
        return self.assignment_scalar(
            values,
            observation_source_component_index(source_id, labels),
            dim,
        )

    def action_index_from_assignment(self, source_id: str) -> int:
        numeric = observation_source_component_index(source_id)
        if numeric is not None:
            return min(max(0, numeric), max(0, len(self.joint_ids) - 1))
        suffix = re.sub(r"[^a-z0-9]+", "_", source_id.rsplit(":", 1)[-1].lower()).strip("_")
        for index, group in enumerate(self.action_groups):
            candidates = [
                group.get("id"),
                group.get("label"),
                group.get("action"),
                group.get("actuator"),
                group.get("joint"),
                group.get("target"),
            ]
            if any(
                re.sub(r"[^a-z0-9]+", "_", str(candidate or "").lower()).strip("_") == suffix
                for candidate in candidates
            ):
                return index
        return 0

    def uses_legacy_local_model_joint_ids(self) -> bool:
        return (
            self.profile.get("source") != "example"
            and self.profile.get("mappingMode") == "manual"
            and self.profile.get("createdBy") == "mujoco_online_gui"
        )

    def model_joint_state_start(self, vector: str) -> int:
        for joint_id in range(int(self.model.njnt)):
            if int(self.model.jnt_type[joint_id]) != int(self.mujoco.mjtJoint.mjJNT_FREE):
                continue
            if int(self.model.jnt_qposadr[joint_id]) != 0:
                continue
            return 7 if vector == "qpos" else 6
        return 0

    def explicit_model_state_address(self, source_id: str, vector: str) -> int | None:
        address_match = re.search(rf":{vector}(\d+)$", source_id)
        if address_match is not None:
            return int(address_match.group(1))
        model_match = re.search(r":model(\d+)$", source_id)
        if model_match is not None:
            return self.model_joint_state_start(vector) + int(model_match.group(1))
        legacy_match = re.search(r":joint(\d+)$", source_id)
        if legacy_match is not None and self.uses_legacy_local_model_joint_ids():
            return self.model_joint_state_start(vector) + int(legacy_match.group(1))
        return None

    def action_index_for_state_address(self, address: int, vector: str) -> int | None:
        for index, joint_id in enumerate(self.joint_ids):
            candidate = (
                int(self.model.jnt_qposadr[joint_id])
                if vector == "qpos"
                else int(self.model.jnt_dofadr[joint_id])
            )
            if candidate == address:
                return index
        return None

    def sensor_assignment_values(self, source_id: str, dim: int) -> Any:
        rest = source_id[len("sensor:"):]
        parts = rest.split(":")
        suffix = parts[-1] if parts else ""
        known_components = {
            "wx", "wy", "wz", "ax", "ay", "az", "vx", "vy", "vz",
            "x", "y", "z", "qw", "qx", "qy", "qz",
        }
        has_component = len(parts) > 1 and (
            suffix.lower() in known_components
            or re.fullmatch(r"(?:item|component)\d+", suffix, flags=re.IGNORECASE) is not None
        )
        sensor_name = ":".join(parts[:-1]) if has_component else rest
        values = sensor_values(self.mujoco, self.model, self.data, sensor_name)
        if not has_component:
            return repeated(values, dim, self.np)
        return self.assignment_scalar(
            values,
            observation_source_component_index(source_id),
            dim,
        )

    def legacy_angular_velocity_sensor_values(
        self,
        source_id: str,
        group: dict[str, Any],
        dim: int,
    ) -> Any | None:
        if not self.uses_legacy_local_model_joint_ids():
            return None
        component_match = re.search(r":W([xyz])$", source_id, flags=re.IGNORECASE)
        if component_match is None or not (
            source_id.startswith("state:qvel:") or source_id.startswith("state:root_ang_vel:")
        ):
            return None
        semantic = " ".join(
            str(group.get(key) or "") for key in ("id", "label", "source")
        ).lower()
        if re.search(r"angular[\s_-]*velocity|ang[\s_-]*vel|gyro|角速度", semantic) is None:
            return None
        for sensor_id in range(int(self.model.nsensor)):
            name = str(
                self.mujoco.mj_id2name(
                    self.model,
                    self.mujoco.mjtObj.mjOBJ_SENSOR,
                    sensor_id,
                )
                or ""
            )
            if re.search(r"angular[\s_-]*velocity|ang[\s_-]*vel|gyro", name, flags=re.IGNORECASE) is None:
                continue
            if int(self.model.sensor_dim[sensor_id]) < 3:
                continue
            start = int(self.model.sensor_adr[sensor_id])
            values = self.data.sensordata[start:start + 3]
            component = component_match.group(1).lower()
            index = 0 if component == "x" else 1 if component == "y" else 2
            self.legacy_angular_velocity_sensor_reads += 1
            return self.assignment_scalar(values, index, dim)
        return None

    def joint_assignment_values(self, source_id: str, dim: int) -> Any | None:
        source_kinds = (
            ("state:joint_pos_raw", "position_raw"),
            ("state:joint_pos", "position"),
            ("state:joint_vel", "velocity"),
        )
        for prefix, kind in source_kinds:
            if source_id != prefix and not source_id.startswith(f"{prefix}:"):
                continue
            values: list[float] = []
            for index, joint_id in enumerate(self.joint_ids):
                if kind == "velocity":
                    values.append(float(self.data.qvel[int(self.model.jnt_dofadr[joint_id])]))
                    continue
                value = float(self.data.qpos[int(self.model.jnt_qposadr[joint_id])])
                if kind == "position":
                    default = float(self.default_targets[index]) if index < self.default_targets.size else 0.0
                    value -= default
                values.append(value)
            if source_id == prefix:
                return repeated(values, dim, self.np)
            vector = "qvel" if kind == "velocity" else "qpos"
            explicit_address = self.explicit_model_state_address(source_id, vector)
            if explicit_address is None:
                return self.assignment_scalar(values, self.action_index_from_assignment(source_id), dim)
            state = self.data.qvel if kind == "velocity" else self.data.qpos
            if explicit_address < 0 or explicit_address >= state.size:
                return self.np.zeros(dim, dtype=self.np.float32)
            value = float(state[explicit_address])
            if kind == "position":
                action_index = self.action_index_for_state_address(explicit_address, "qpos")
                default = (
                    float(self.default_targets[action_index])
                    if action_index is not None and action_index < self.default_targets.size
                    else float(self.model.qpos0[explicit_address])
                )
                value -= default
            return repeated([value], dim, self.np)
        return None

    def virtual_servo_assignment_values(self, source_id: str, dim: int) -> Any | None:
        position_prefix = "runtime:virtual_servo:position_error"
        velocity_prefix = "runtime:virtual_servo:velocity"
        if source_id == position_prefix or source_id.startswith(f"{position_prefix}:"):
            values = self.virtual_servo_position - self.default_targets
            if source_id == position_prefix:
                return repeated(values, dim, self.np)
            return self.assignment_scalar(values, self.action_index_from_assignment(source_id), dim)
        if source_id == velocity_prefix or source_id.startswith(f"{velocity_prefix}:"):
            values = self.virtual_servo_velocity
            if source_id == velocity_prefix:
                return repeated(values, dim, self.np)
            return self.assignment_scalar(values, self.action_index_from_assignment(source_id), dim)
        return None

    def update_virtual_servo(self, raw_targets: Any) -> Any:
        if not self.virtual_servo_params:
            return raw_targets
        kp = max(0.0, float(self.virtual_servo_params.get("kp") if self.virtual_servo_params.get("kp") is not None else 35.0))
        kd = max(0.0, float(self.virtual_servo_params.get("kd") if self.virtual_servo_params.get("kd") is not None else 1.2))
        inertia = max(1.0e-6, float(self.virtual_servo_params.get("inertia") if self.virtual_servo_params.get("inertia") is not None else 1.0))
        dt = max(1.0e-6, float(self.virtual_servo_params.get("controlDt") if self.virtual_servo_params.get("controlDt") is not None else float(self.model.opt.timestep) * self.decimation))
        smoothing = self.np.clip(float(self.virtual_servo_params.get("actionSmoothing") if self.virtual_servo_params.get("actionSmoothing") is not None else 0.35), 0.0, 1.0)
        clamp_position = self.virtual_servo_params.get("clampPosition", True) is not False
        error = self.virtual_servo_target - self.virtual_servo_position
        acceleration = (kp * error - kd * self.virtual_servo_velocity) / inertia
        self.virtual_servo_velocity = (self.virtual_servo_velocity + acceleration * dt).astype(self.np.float32, copy=False)
        self.virtual_servo_position = (self.virtual_servo_position + self.virtual_servo_velocity * dt).astype(self.np.float32, copy=False)
        if clamp_position:
            self.virtual_servo_position = self.np.clip(self.virtual_servo_position, self.virtual_servo_lower, self.virtual_servo_upper)
        bounded = self.np.asarray(raw_targets, dtype=self.np.float32).reshape(-1)[:self.action_dim]
        if clamp_position:
            bounded = self.np.clip(bounded, self.virtual_servo_lower, self.virtual_servo_upper)
        self.virtual_servo_target = ((1.0 - smoothing) * self.virtual_servo_target + smoothing * bounded).astype(self.np.float32, copy=False)
        return self.virtual_servo_target.copy()

    def action_history_assignment_values(self, source_id: str, dim: int) -> Any | None:
        if source_id == "history:previous_action":
            return repeated(self.last_action, dim, self.np)
        if source_id.startswith("history:previous_action:"):
            return self.assignment_scalar(
                self.last_action,
                observation_source_component_index(source_id),
                dim,
            )
        if not source_id.startswith("history:action_history"):
            return None
        scalar = re.search(r":f(\d+):a(\d+)$", source_id, flags=re.IGNORECASE)
        if scalar:
            frame_index = max(0, int(scalar.group(1)))
            action_index = max(0, int(scalar.group(2)))
            adapter = next(
                (
                    item
                    for item in self.adapters
                    if item.get("type") == "action_history" and item.get("enabled")
                ),
                None,
            )
            params = (adapter or {}).get("params") or {}
            frame_count = max(1, int(params.get("frames") or len(self.action_history)))
            order = str(params.get("order") or "old_to_new")
            history_index = frame_index if order == "new_to_old" else max(0, frame_count - 1 - frame_index)
            history_index = min(history_index, max(0, len(self.action_history) - 1))
            return self.assignment_scalar(self.action_history[history_index], action_index, dim)
        return repeated(self.np.concatenate(self.action_history), dim, self.np)

    def signal_history_adapter(self, source_id: str) -> tuple[dict[str, Any], int | None] | None:
        prefix = "history:signal:"
        if not source_id.startswith(prefix):
            return None
        item_match = re.search(r":item(\d+)$", source_id, flags=re.IGNORECASE)
        adapter_id = re.sub(r":item\d+$", "", source_id[len(prefix):], flags=re.IGNORECASE)
        adapter = next(
            (
                item
                for item in self.adapters
                if item.get("type") == "signal_history"
                and item.get("enabled")
                and str(item.get("id") or "") == adapter_id
            ),
            None,
        )
        if adapter is None:
            return None
        return adapter, (max(0, int(item_match.group(1))) if item_match else None)

    def signal_history_current(self, adapter: dict[str, Any], group: dict[str, Any]) -> Any:
        params = adapter.get("params") or {}
        source_dim = max(1, int(params.get("sourceDim") or 1))
        source_id = str(params.get("sourceId") or "").strip()
        if not source_id or source_id.startswith("history:signal:"):
            return self.np.zeros(source_dim, dtype=self.np.float32)
        source_group = {
            **group,
            "id": f"runtime-signal-history-source:{adapter.get('id') or ''}",
            "label": source_id,
            "source": source_id,
            "sourceType": "manual",
            "targetMode": "manual",
            "targets": [],
            "repeat": None,
            "transform": None,
            "manual": True,
            "dim": source_dim,
            "span": f"[0:{source_dim}]",
        }
        raw = self.assigned_source_values(source_id, source_group, source_dim)
        if raw is None:
            raw = self.np.zeros(source_dim, dtype=self.np.float32)
        current = repeated(raw, source_dim, self.np).astype(self.np.float32, copy=True)
        scale = float(params.get("scale") if params.get("scale") is not None else 1.0)
        bias = float(params.get("bias") or 0.0)
        component_scale = self.np.asarray(
            [float(item) for item in re.split(r"[,\s]+", str(params.get("componentScale") or "").strip()) if item],
            dtype=self.np.float32,
        )
        component_bias = self.np.asarray(
            [float(item) for item in re.split(r"[,\s]+", str(params.get("componentBias") or "").strip()) if item],
            dtype=self.np.float32,
        )
        current *= scale
        if component_scale.size:
            component_count = min(source_dim, component_scale.size)
            current[:component_count] *= component_scale[:component_count]
        current += bias
        if component_bias.size:
            component_count = min(source_dim, component_bias.size)
            current[:component_count] += component_bias[:component_count]
        clip_parts = [item for item in re.split(r"[,\s]+", str(params.get("clip") or "-inf, inf").strip()) if item]
        clip_min = float(clip_parts[0]) if clip_parts else -float("inf")
        clip_max = float(clip_parts[1]) if len(clip_parts) > 1 else float("inf")
        return self.np.clip(current, clip_min, clip_max).astype(self.np.float32, copy=False)

    def signal_history_values(self, adapter: dict[str, Any], group: dict[str, Any]) -> Any:
        params = adapter.get("params") or {}
        adapter_id = str(adapter.get("id") or "")
        source_dim = max(1, int(params.get("sourceDim") or 1))
        frame_count = max(1, int(params.get("frames") or 1))
        include_current = bool(params.get("includeCurrent", True))
        past_count = max(0, frame_count - (1 if include_current else 0))
        current = self.signal_history_current(adapter, group)
        state = self.signal_history_states.get(adapter_id)
        if state and state.get("step") == self.policy_step:
            output = self.np.asarray(state.get("output"), dtype=self.np.float32).reshape(-1)
            if output.size == source_dim * frame_count:
                return output.copy()
        frames = list((state or {}).get("frames") or [])
        if len(frames) != past_count or any(self.np.asarray(frame).size != source_dim for frame in frames):
            seed = current if str(params.get("initialize") or "zero") == "repeat_first" else self.np.zeros(source_dim, dtype=self.np.float32)
            frames = [seed.copy() for _ in range(past_count)]
        ordered = [current, *frames] if include_current else list(frames)
        if str(params.get("order") or "new_to_old") == "old_to_new":
            ordered.reverse()
        output = self.np.concatenate(ordered).astype(self.np.float32, copy=False)
        self.signal_history_states[adapter_id] = {
            "frames": [current.copy(), *frames][:past_count],
            "step": self.policy_step,
            "output": output.copy(),
        }
        return output

    def assigned_source_values(self, source_id: str, group: dict[str, Any], dim: int) -> Any | None:
        signal_history = self.signal_history_adapter(source_id)
        if signal_history is not None:
            adapter, component = signal_history
            values = self.signal_history_values(adapter, group)
            if component is None:
                return repeated(values, dim, self.np)
            return self.assignment_scalar(values, component, dim)
        if source_id.startswith("sensor:"):
            return self.sensor_assignment_values(source_id, dim)

        legacy_angular_velocity = self.legacy_angular_velocity_sensor_values(source_id, group, dim)
        if legacy_angular_velocity is not None:
            return legacy_angular_velocity

        vector_sources = [
            (
                "state:root_quat",
                self.data.qpos[3:7],
                ("Qw", "Qx", "Qy", "Qz"),
            ),
            (
                "state:root_ang_vel",
                self.data.qvel[3:6],
                ("Wx", "Wy", "Wz"),
            ),
            (
                "derived:projected_gravity",
                self.gravity_values([str(item) for item in (group.get("targets") or [])]),
                ("X", "Y", "Z"),
            ),
            (
                "derived:base_euler",
                self.base_euler([str(item) for item in (group.get("targets") or [])]),
                ("Roll", "Pitch", "Yaw"),
            ),
        ]
        local_linear_velocity = self.sensor_or_none(["local_linvel", "local_linvel_pelvis"])
        if local_linear_velocity is not None:
            vector_sources.append(
                ("derived:local_linvel", local_linear_velocity, ("Vx", "Vy", "Vz"))
            )
        for prefix, values, labels in vector_sources:
            assigned = self.assignment_vector(source_id, prefix, values, dim, labels)
            if assigned is not None:
                return assigned

        if source_id == "state:qpos:joints":
            values = [
                float(self.data.qpos[int(self.model.jnt_qposadr[joint_id])])
                for joint_id in self.joint_ids
            ]
            return repeated(values, dim, self.np)
        assigned = self.assignment_vector(
            source_id,
            "state:qpos",
            self.data.qpos,
            dim,
            ("X", "Y", "Z", "Qw", "Qx", "Qy", "Qz"),
        )
        if assigned is not None:
            return assigned
        if source_id == "state:qvel:joints":
            values = [
                float(self.data.qvel[int(self.model.jnt_dofadr[joint_id])])
                for joint_id in self.joint_ids
            ]
            return repeated(values, dim, self.np)
        assigned = self.assignment_vector(
            source_id,
            "state:qvel",
            self.data.qvel,
            dim,
            ("Vx", "Vy", "Vz", "Wx", "Wy", "Wz"),
        )
        if assigned is not None:
            return assigned

        assigned = self.joint_assignment_values(source_id, dim)
        if assigned is not None:
            return assigned

        assigned = self.virtual_servo_assignment_values(source_id, dim)
        if assigned is not None:
            return assigned

        assigned = self.constant_assignment_values(source_id, dim)
        if assigned is not None:
            return assigned

        if source_id == "runtime:command_vxyaw":
            return repeated(self.command_values(max(dim, int(self.command.size))), dim, self.np)
        if source_id.startswith("runtime:command_vxyaw:"):
            values = self.command_values(max(dim, int(self.command.size)))
            return self.assignment_scalar(
                values,
                observation_source_component_index(source_id, ("vx", "vy", "yaw")),
                dim,
            )
        if source_id == "runtime:motor_targets":
            return repeated(self.motor_targets, dim, self.np)
        if source_id.startswith("runtime:motor_targets:"):
            return self.assignment_scalar(
                self.motor_targets,
                self.action_index_from_assignment(source_id),
                dim,
            )
        if source_id == "runtime:foot_contact" or source_id.startswith("runtime:foot_contact:"):
            adapter = next(
                (
                    item
                    for item in self.adapters
                    if item.get("type") == "foot_contact" and item.get("enabled")
                ),
                None,
            )
            params = (adapter or {}).get("params") or {}
            feet = [
                item.strip()
                for item in str(params.get("footGeoms") or "").replace(";", ",").split(",")
                if item.strip()
            ]
            values = self.foot_contacts(feet, max(dim, len(feet)))
            if source_id == "runtime:foot_contact":
                return repeated(values, dim, self.np)
            return self.assignment_scalar(
                values,
                observation_source_component_index(source_id),
                dim,
            )

        assigned = self.action_history_assignment_values(source_id, dim)
        if assigned is not None:
            return assigned

        if source_id in {"clock:phase_2", "clock:phase_4"}:
            return repeated(self.phase_values(dim), dim, self.np)
        if source_id.startswith("clock:phase_2:") or source_id.startswith("clock:phase_4:"):
            phase_dim = 4 if source_id.startswith("clock:phase_4:") else 2
            values = self.phase_values(phase_dim)
            return self.assignment_scalar(
                values,
                observation_source_component_index(
                    source_id,
                    ("cosL", "cosR", "sinL", "sinR") if phase_dim == 4 else ("cos", "sin"),
                ),
                dim,
            )
        return None

    def assignment_should_yield_to_runtime_semantic(self, group: dict[str, Any]) -> bool:
        group_id = str(group.get("id") or "")
        source_type = str(group.get("sourceType") or "")
        lower = f"{group_id} {group.get('label') or ''} {group.get('source') or ''}".lower()
        walk_these_ways = (
            self.project_id == "walk-these-ways-go1"
            or "walk_these_ways" in self.family
            or "walk-these-ways" in self.family
            or "quadruped_history_gait" in self.family
        )
        if walk_these_ways:
            if source_type in {
                "command",
                "clock_phase",
                "joint_position",
                "joint_velocity",
                "previous_action",
                "base_orientation",
            }:
                return True
            if group_id in {"mob_command", "clock", "joint_pos", "joint_vel", "actions", "previous_actions", "gravity"}:
                return True
            if any(
                marker in lower
                for marker in {
                    "gait command",
                    "clock",
                    "joint position",
                    "joint velocity",
                    "current action",
                    "previous action",
                    "last onnx action",
                    "gravity",
                }
            ):
                return True
        leap_like = (
            self.project_id == "playground-leap"
            or "leap" in self.family
            or "hand_object" in self.family
            or "reorient" in self.family
        )
        return leap_like and group_id in {"joint_angles", "qpos_error", "cube_position", "cube_orientation"}

    def assigned_values_for_group(self, group: dict[str, Any]) -> Any | None:
        if self.assignment_should_yield_to_runtime_semantic(group):
            return None
        group_id = str(group.get("id") or "")
        dim = int(group.get("dim") or 0)
        source_id = self.observation_assignments.get(group_id)
        if source_id:
            return self.assigned_source_values(source_id, group, dim)
        start = frame_span_start(group.get("span"))
        scalar_values: list[Any] = []
        for index in range(dim):
            target_id = f"obs:{start + index}:{start + index + 1}"
            scalar_source_id = self.observation_assignments.get(target_id)
            if not scalar_source_id:
                return None
            scalar_group = {
                **group,
                "id": target_id,
                "dim": 1,
                "span": f"[{start + index}:{start + index + 1}]",
            }
            values = self.assigned_source_values(scalar_source_id, scalar_group, 1)
            if values is None:
                return None
            scalar_values.append(values)
        if not scalar_values:
            return None
        return self.np.concatenate(scalar_values).astype(self.np.float32, copy=False)

    def group_values(self, group: dict[str, Any]) -> Any:
        dim = int(group.get("dim") or 0)
        assigned_values = self.assigned_values_for_group(group)
        if assigned_values is not None:
            return apply_transform(assigned_values, group.get("transform"), self.np)
        source_type = str(group.get("sourceType") or "")
        targets = [str(item) for item in (group.get("targets") or [])]
        lower = f"{group.get('id') or ''} {group.get('label') or ''} {group.get('source') or ''}".lower()
        leaf_index = manual_group_leaf_index(group)
        if not targets and source_type in {"sensor", "base_angular_velocity"}:
            label = str(group.get("label") or "")
            if label.startswith("sensor:"):
                targets = [label.split(":", 2)[1]]
        if not targets and source_type in {"joint_position", "joint_velocity"} and leaf_index is not None and leaf_index < len(self.joint_ids):
            joint_name = self.mujoco.mj_id2name(self.model, self.mujoco.mjtObj.mjOBJ_JOINT, self.joint_ids[leaf_index])
            if joint_name:
                targets = [str(joint_name)]
        if source_type == "sensor" and self.project_id == "playground-leap" and (group.get("id") == "cube_position" or "cube position" in lower):
            return apply_transform(repeated(self.leap_position_error(), dim, self.np), group.get("transform"), self.np)
        if source_type in {"sensor", "base_angular_velocity"}:
            values = sensor_values(self.mujoco, self.model, self.data, targets[0] if targets else str(group.get("id") or ""))
            return apply_transform(manual_group_values(values, group, dim, self.np), group.get("transform"), self.np)
        if source_type == "command":
            source_dim = max(dim, int(self.command.size), (leaf_index + 1) if leaf_index is not None else 0)
            values = self.command_values(source_dim)
            return apply_transform(manual_group_values(values, group, dim, self.np), group.get("transform"), self.np)
        if source_type == "joint_position":
            if self.actuator_session is not None and len(self.policy_to_model_order) == self.action_dim:
                model_positions = self.np.asarray(
                    [float(self.data.qpos[int(self.model.jnt_qposadr[item])]) for item in self.joint_ids],
                    dtype=self.np.float32,
                )
                values = self.np.asarray(
                    [model_positions[self.policy_to_model_order[index]] - self.actuator_policy_default_joint_pos[index] for index in range(min(dim, self.action_dim))],
                    dtype=self.np.float32,
                )
                values = repeated(values, dim, self.np)
            else:
                values = repeated([self.joint_position(name) for name in targets], dim, self.np)
            return apply_transform(values, group.get("transform"), self.np)
        if source_type == "joint_velocity":
            if self.actuator_session is not None and len(self.policy_to_model_order) == self.action_dim:
                model_velocities = self.np.asarray(
                    [float(self.data.qvel[int(self.model.jnt_dofadr[item])]) for item in self.joint_ids],
                    dtype=self.np.float32,
                )
                values = self.np.asarray(
                    [model_velocities[self.policy_to_model_order[index]] for index in range(min(dim, self.action_dim))],
                    dtype=self.np.float32,
                )
                values *= self.actuator_policy_joint_velocity_scale
                values = repeated(values, dim, self.np)
            else:
                values = repeated([self.joint_velocity(name) for name in targets], dim, self.np)
            return apply_transform(values, group.get("transform"), self.np)
        if source_type in {"previous_action", "action_history"}:
            walk_these_ways_history = (
                "walk_these_ways" in self.family or self.project_id == "walk-these-ways-go1"
            ) and (group.get("id") == "previous_actions" or "previous" in lower)
            if walk_these_ways_history:
                values = self.action_history[1]
            elif dim > self.action_dim:
                values = self.np.concatenate(self.action_history)
            else:
                values = self.action_history[0]
            return apply_transform(manual_group_values(values, group, dim, self.np), group.get("transform"), self.np)
        if source_type == "virtual_servo":
            values = self.virtual_servo_velocity if ("velocity" in lower or "dq_hat" in lower) else self.virtual_servo_position - self.default_targets
            return apply_transform(repeated(values, dim, self.np), group.get("transform"), self.np)
        if source_type == "state_pool":
            if "target error" in lower:
                positions = self.np.asarray([float(self.data.qpos[int(self.model.jnt_qposadr[item])]) for item in self.joint_ids], dtype=self.np.float32)
                values = positions - self.motor_targets
            else:
                values = self.motor_targets
            return apply_transform(repeated(values, dim, self.np), group.get("transform"), self.np)
        if source_type == "contact":
            return apply_transform(self.contacts(targets, dim), group.get("transform"), self.np)
        if source_type == "clock_phase":
            phase_dim = 4 if "4" in self.phase_format else 2
            values = self.phase_values(max(dim, phase_dim, (leaf_index + 1) if leaf_index is not None else 0))
            return apply_transform(manual_group_values(values, group, dim, self.np), group.get("transform"), self.np)
        if source_type == "base_orientation":
            if self.project_id == "playground-leap" and (group.get("id") == "cube_orientation" or "cube orientation" in lower):
                values = self.leap_orientation_error()
            elif "euler" in lower or "orientation" in lower:
                values = self.base_euler(targets)
            else:
                values = self.gravity_values(targets)
            return apply_transform(repeated(values, dim, self.np), group.get("transform"), self.np)
        if source_type == "custom" and self.project_id == "playground-leap" and group.get("id") == "joint_angles":
            values = [float(self.data.qpos[int(self.model.jnt_qposadr[item])]) for item in self.joint_ids]
            return apply_transform(repeated(values, dim, self.np), group.get("transform"), self.np)
        if source_type == "reference_motion":
            if not self.reference_ready:
                return self.np.zeros(dim, dtype=self.np.float32)
            if group.get("id") == "motion_command" or "reference joint motion" in lower:
                return repeated(self.np.concatenate([self.reference_joint_pos, self.reference_joint_vel]), dim, self.np)
            if group.get("id") == "motion_anchor_ori" or "anchor orientation" in lower:
                return repeated(self.reference_anchor_orientation(), dim, self.np)
            return self.np.zeros(dim, dtype=self.np.float32)
        raise RuntimeError(f"Native policy viewer does not yet support observation sourceType={source_type!r} ({group.get('label')}).")

    def build_observation(self) -> Any:
        if self.virtual_servo_params and self.policy_step == 0 and self.virtual_servo_params.get("zeroFirstPolicyInput", True) is not False:
            return self.np.zeros(self.obs_dim, dtype=self.np.float32)
        if not self.frame_stack:
            values = [self.group_values(group) for group in self.groups]
            return self.np.concatenate(values).astype(self.np.float32, copy=False)
        frame_count = max(1, int(self.frame_stack.get("frames") or 1))
        frame_dim = max(1, int(self.frame_stack.get("frameDim") or 1))
        if self.actuator_session is not None:
            if not self.frame_history or len(self.frame_history) != frame_count:
                self.frame_history = [self.np.zeros(frame_dim, dtype=self.np.float32) for _ in range(frame_count)]
            ordered = list(reversed(self.frame_history)) if self.frame_stack.get("order") == "new_to_old" else self.frame_history
            return self.np.concatenate(ordered).astype(self.np.float32, copy=False)
        frame = self.np.zeros(frame_dim, dtype=self.np.float32)
        for group in self.groups:
            repeat = group.get("repeat") or {}
            group_dim = int(repeat.get("frameDim") or group.get("dim") or 0)
            frame_group = {**group, "dim": group_dim}
            start = frame_span_start(group.get("span"))
            if start >= frame_dim:
                continue
            values = self.group_values(frame_group)[:frame_dim - start]
            frame[start:start + values.size] = values
        if not self.frame_history or len(self.frame_history) != frame_count:
            initialize = str(self.frame_stack.get("initialize") or "zero")
            seed = frame if initialize == "repeat_first" else self.np.zeros(frame_dim, dtype=self.np.float32)
            self.frame_history = [seed.copy() for _ in range(frame_count)]
        self.frame_history = [*self.frame_history[1:], frame.copy()]
        ordered = list(reversed(self.frame_history)) if self.frame_stack.get("order") == "new_to_old" else self.frame_history
        observation = self.np.concatenate(ordered).astype(self.np.float32, copy=False)
        if self.project_id == "xbot":
            observation = self.np.clip(observation, -18.0, 18.0)
        return observation

    def push_actuator_net_observation(self) -> None:
        if not self.frame_stack:
            return
        frame_count = max(1, int(self.frame_stack.get("frames") or 1))
        frame_dim = max(1, int(self.frame_stack.get("frameDim") or 1))
        frame = self.np.zeros(frame_dim, dtype=self.np.float32)
        for group in self.groups:
            repeat = group.get("repeat") or {}
            group_dim = int(repeat.get("frameDim") or group.get("dim") or 0)
            values = self.group_values({**group, "dim": group_dim})
            start = frame_span_start(group.get("span"))
            if start < frame_dim:
                values = values[:frame_dim - start]
                frame[start:start + values.size] = values
        if not self.frame_history or len(self.frame_history) != frame_count:
            self.frame_history = [self.np.zeros(frame_dim, dtype=self.np.float32) for _ in range(frame_count)]
        self.frame_history = [*self.frame_history[1:], frame]

    def should_infer(self, simulation_step: int) -> bool:
        policy_step = int(simulation_step) - self.motor_initial_delay
        return policy_step >= 0 and policy_step % self.decimation == 0

    def infer(self) -> None:
        if self.actuator_session is not None and self.policy_step > 0:
            self.push_actuator_net_observation()
        observation = self.build_observation()
        if observation.size != self.obs_dim:
            raise RuntimeError(f"Built observation has {observation.size} values; profile requires {self.obs_dim}.")
        if self.first_observation is None:
            self.first_observation = observation.copy()
        feeds = {self.input_name: observation.reshape(1, -1)}
        if len(self.session.get_inputs()) > 1:
            for item in self.session.get_inputs()[1:]:
                if item.name == str(self.reference_params.get("timestepSource") or "time_step") or item.name == "time_step":
                    feeds[item.name] = self.np.asarray([[self.reference_time_step]], dtype=self.np.float32)
        results = self.session.run(self.output_names, feeds)
        outputs = dict(zip(self.output_names, results))
        action = self.np.asarray(outputs[self.output_name], dtype=self.np.float32).reshape(-1)[:self.action_dim]
        action = action * self.idle_action_scale()
        if self.first_action is None:
            self.first_action = action.copy()
        if self.reference_params:
            self.update_reference_outputs(outputs)
            self.reference_time_step = (self.reference_time_step + 1) % self.reference_max_time_step
        if self.actuator_session is not None:
            action = self.np.clip(action, -10.0, 10.0)
        self.action_history = [action.copy(), *self.action_history[:2]]
        self.last_action = action
        incremental_targets = self.incremental_motor_targets
        desired = self.previous_motor_targets.copy() if incremental_targets else self.default_targets.copy()
        count = min(len(self.actuator_ids), action.size)
        virtual_action_clip = max(1.0e-6, float(self.virtual_servo_params.get("actionClip") if self.virtual_servo_params.get("actionClip") is not None else 1.0)) if self.virtual_servo_params else float("inf")
        for index in range(count):
            scale = float(self.motor_scales[index])
            action_value = self.np.clip(action[index], -virtual_action_clip, virtual_action_clip)
            desired[index] += action_value * scale * self.signs[index] + self.offsets[index]
            actuator_id = self.actuator_ids[index]
            if incremental_targets and int(self.model.actuator_ctrllimited[actuator_id]):
                desired[index] = self.np.clip(desired[index], self.model.actuator_ctrlrange[actuator_id, 0], self.model.actuator_ctrlrange[actuator_id, 1])
        if self.max_motor_velocity > 0:
            control_dt = float(self.model.opt.timestep) * self.decimation
            delta = self.max_motor_velocity * control_dt
            desired = self.np.clip(desired, self.previous_motor_targets - delta, self.previous_motor_targets + delta)
        if self.virtual_servo_params:
            desired = self.update_virtual_servo(desired)
        self.motor_targets = desired.astype(self.np.float32, copy=False)
        self.previous_motor_targets = self.motor_targets.copy()
        if self.actuator_session is None:
            self.apply_control()
        self.advance_command_conditioned_phase()
        self.policy_step += 1

    def apply_actuator_net_control(self) -> None:
        if self.actuator_session is None:
            return
        scaled = self.np.zeros(self.action_dim, dtype=self.np.float32)
        for model_index in range(self.action_dim):
            policy_index = self.model_to_policy_order[model_index]
            hip_scale = self.actuator_hip_scale if model_index in self.actuator_hip_indices else 1.0
            scaled[model_index] = self.last_action[policy_index] * self.actuator_action_scale * hip_scale
        self.actuator_lag = [*self.actuator_lag[1:], scaled]
        delayed = self.actuator_lag[0]
        target = self.actuator_default_joint_pos + delayed
        joint_position = self.np.asarray(
            [float(self.data.qpos[int(self.model.jnt_qposadr[item])]) for item in self.joint_ids],
            dtype=self.np.float32,
        )
        joint_velocity = self.np.asarray(
            [float(self.data.qvel[int(self.model.jnt_dofadr[item])]) for item in self.joint_ids],
            dtype=self.np.float32,
        )
        joint_error = joint_position - target
        actuator_input = self.np.stack(
            [
                joint_error,
                self.actuator_joint_error[0],
                self.actuator_joint_error[1],
                joint_velocity,
                self.actuator_joint_velocity[0],
                self.actuator_joint_velocity[1],
            ],
            axis=1,
        ).astype(self.np.float32, copy=False)
        values = self.actuator_session.run(
            [self.actuator_output_name],
            {self.actuator_input_name: actuator_input},
        )[0]
        torques = self.np.asarray(values, dtype=self.np.float32).reshape(-1)[:self.action_dim]
        torques = self.np.clip(torques, -self.actuator_torque_limit, self.actuator_torque_limit)
        for index, actuator_id in enumerate(self.actuator_ids):
            self.data.ctrl[actuator_id] = torques[index]
        self.actuator_joint_error = [joint_error.copy(), self.actuator_joint_error[0]]
        self.actuator_joint_velocity = [joint_velocity.copy(), self.actuator_joint_velocity[0]]

    def apply_control(self) -> None:
        if self.actuator_session is not None:
            self.apply_actuator_net_control()
            return
        for index, actuator_id in enumerate(self.actuator_ids):
            dynamics = self.actuator_dynamics[index]
            if dynamics.get("type") == "dc_position":
                qpos_id = int(self.model.jnt_qposadr[self.joint_ids[index]])
                qvel_id = int(self.model.jnt_dofadr[self.joint_ids[index]])
                voltage = (float(dynamics["positionGain"]) * (float(self.motor_targets[index]) - float(self.data.qpos[qpos_id]))
                           - float(dynamics["velocityGain"]) * float(self.data.qvel[qvel_id]))
                limit = float(dynamics["voltageLimit"])
                self.data.ctrl[actuator_id] = self.np.clip(voltage, -limit, limit)
                continue
            mode = self.modes[index].lower()
            action_group = ((self.profile.get("action") or {}).get("groups") or [])[index]
            action_text = f"{action_group.get('mode') or ''} {action_group.get('scale') or ''} {action_group.get('limit') or ''} {action_group.get('source') or ''}".lower()
            if mode == "pd" and any(word in action_text for word in ["torque", "tau", "pd motor"]):
                qpos_id = int(self.model.jnt_qposadr[self.joint_ids[index]])
                qvel_id = int(self.model.jnt_dofadr[self.joint_ids[index]])
                target = float(self.last_action[index]) * self.scales[index] * self.signs[index] + self.offsets[index]
                if self.configured_target_mask[index] or any(word in action_text for word in ["default", "home", "keyframe", "knees_bent"]):
                    target += float(self.default_targets[index])
                torque = (target - float(self.data.qpos[qpos_id])) * self.kps[index] - float(self.data.qvel[qvel_id]) * self.kds[index]
                limit = self.limits[index]
                self.data.ctrl[actuator_id] = self.np.clip(torque, -limit, limit)
            else:
                self.data.ctrl[actuator_id] = self.motor_targets[index]


def launch_viewer(
    mujoco: Any,
    model: Any,
    data: Any,
    root: Path,
    manifest: dict[str, Any],
    profile: dict[str, Any] | None,
    seconds: float,
    command_vx: float | None,
    policy_control: bool,
) -> None:
    import mujoco.viewer

    controller = ProfilePolicyController(mujoco, model, data, root, manifest, profile, command_vx) if policy_control and profile else None
    if controller is not None:
        controller.print_remote_control_help()
    key_callback = controller.handle_remote_key if controller is not None and controller.remote_control_enabled else None
    with mujoco.viewer.launch_passive(
        model,
        data,
        key_callback=key_callback,
        show_left_ui=True,
        show_right_ui=True,
    ) as viewer:
        camera_body_ids = robot_camera_body_ids(model)
        lookat, distance = robot_camera_pose(model, data, camera_body_ids)
        viewer.cam.distance = distance * 1.45
        viewer.cam.azimuth = 135
        viewer.cam.elevation = -18
        viewer.cam.lookat[:] = lookat
        viewer.sync()
        timestep = max(float(model.opt.timestep), 1.0e-6)
        start = time.perf_counter()
        last_wall_time = start
        last_viewer_sync = start
        accumulator = 0.0
        simulation_step = 0
        while viewer.is_running():
            now = time.perf_counter()
            if seconds > 0 and now - start >= seconds:
                break
            accumulator, steps_to_run = realtime_step_budget(accumulator, now - last_wall_time, timestep)
            last_wall_time = now

            for _ in range(steps_to_run):
                if controller is not None and controller.should_infer(simulation_step):
                    controller.infer()
                if controller is not None:
                    controller.apply_control()
                mujoco.mj_step(model, data)
                simulation_step += 1

            now = time.perf_counter()
            if now - last_viewer_sync >= VIEWER_RENDER_INTERVAL_SECONDS:
                lookat, _ = robot_camera_pose(model, data, camera_body_ids)
                viewer.cam.lookat[:] = lookat
                viewer.sync()
                last_viewer_sync = time.perf_counter()

            if steps_to_run == 0:
                until_step = max(0.0, timestep - accumulator)
                until_sync = max(0.0, VIEWER_RENDER_INTERVAL_SECONDS - (time.perf_counter() - last_viewer_sync))
                sleep_for = min(until_step, until_sync, 0.002)
                if sleep_for > 0:
                    time.sleep(sleep_for)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load and validate a StackForce export in native MuJoCo.")
    parser.add_argument("--steps", type=int, default=240, help="Native MuJoCo smoke-test steps.")
    parser.add_argument("--validate-policy", action="store_true", help="Open the ONNX policy and validate profile dimensions.")
    parser.add_argument("--render", type=Path, default=None, help="Write a native MuJoCo PNG frame.")
    parser.add_argument("--render-width", type=int, default=960)
    parser.add_argument("--render-height", type=int, default=720)
    parser.add_argument("--viewer", action="store_true", help="Open the native passive MuJoCo viewer after validation.")
    parser.add_argument("--viewer-seconds", type=float, default=0.0, help="Close the viewer after N seconds; zero waits for the user.")
    parser.add_argument("--command-vx", type=float, default=None, help="Optional initial forward command override; profile defaults are used when omitted.")
    parser.add_argument("--policy-control", action="store_true", help="Execute profile-driven ONNX control during the headless smoke test.")
    parser.add_argument("--min-root-height", type=float, default=None, help="Fail when the controlled root drops below this height during the smoke test.")
    parser.add_argument("--no-policy-control", action="store_true", help="Run physics without ONNX policy control in the viewer.")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    try:
        import mujoco
        import numpy as np
    except ImportError as error:
        raise RuntimeError("Install sim2sim/requirements.txt before running this package.") from error

    root = package_root()
    manifest_path = root / "manifest.json"
    manifest = load_json(manifest_path)
    model_value = (manifest.get("module") or {}).get("asset_root")
    model_path = resolve_package_path(root, model_value, "root model")
    profile = load_profile(root, manifest)
    validation_scene = (((profile or {}).get("runtime") or {}).get("pose") or {}).get("validationSceneFile")
    if validation_scene:
        if not isinstance(validation_scene, str) or Path(validation_scene).name != validation_scene or not validation_scene.startswith("__stackforce_validation_"):
            raise RuntimeError("Invalid validation scene filename")
        model_path = resolve_package_path(root, str((model_path.parent / validation_scene).relative_to(root)), "validation terrain scene")
    keyframe_qpos_lengths = load_declared_keyframe_qpos_lengths(model_path)
    model, generated_ground = load_model_with_ground(mujoco, model_path, root / "sim2sim")
    data = mujoco.MjData(model)
    reset_keyframe = reset_model(mujoco, model, data, profile, keyframe_qpos_lengths)
    controlled_root_id = controlled_root_body_id(model)
    controlled_root_name = (
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, controlled_root_id)
        if controlled_root_id is not None
        else None
    )
    initial_root_world = (
        [float(value) for value in data.xpos[controlled_root_id]]
        if controlled_root_id is not None
        else None
    )
    start_qpos = np.asarray(data.qpos, dtype=np.float64).copy()
    start_time = float(data.time)
    initial_contact_count = int(data.ncon)
    initial_min_contact_distance = min(
        (float(data.contact[index].dist) for index in range(initial_contact_count)),
        default=0.0,
    )
    headless_controller = (
        ProfilePolicyController(mujoco, model, data, root, manifest, profile, args.command_vx)
        if args.policy_control and profile
        else None
    )
    min_root_height = float(data.xpos[controlled_root_id][2]) if controlled_root_id is not None else None
    for simulation_step in range(max(args.steps, 0)):
        if headless_controller is not None and headless_controller.should_infer(simulation_step):
            headless_controller.infer()
        if headless_controller is not None:
            headless_controller.apply_control()
        mujoco.mj_step(model, data)
        if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
            raise RuntimeError(f"MuJoCo state became non-finite at step {simulation_step + 1}")
        if controlled_root_id is not None:
            min_root_height = min(float(min_root_height), float(data.xpos[controlled_root_id][2]))
    if args.min_root_height is not None and min_root_height is not None and min_root_height < args.min_root_height:
        raise RuntimeError(
            f"Controlled root fell below minimum height: min={min_root_height:.6f}, required={args.min_root_height:.6f}"
        )

    policy_result = validate_policy(root, manifest, profile) if args.validate_policy else {"status": "not_checked"}
    if args.render:
        render_frame(mujoco, model, data, args.render.resolve(), args.render_width, args.render_height)

    report = {
        "schema_version": "1.0",
        "status": "pass",
        "package": manifest.get("name"),
        "model": {
            "path": str(model_path.relative_to(root)),
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "nsensor": int(model.nsensor),
            "reset_keyframe": reset_keyframe,
            "generated_ground": generated_ground,
        },
        "simulation": {
            "steps": max(args.steps, 0),
            "time_start": start_time,
            "time_end": float(data.time),
            "qpos_delta_l2": float(np.linalg.norm(np.asarray(data.qpos) - start_qpos)),
            "initial_contact_count": initial_contact_count,
            "initial_min_contact_distance": initial_min_contact_distance,
            "controlled_root_body": controlled_root_name,
            "initial_root_world": initial_root_world,
            "final_root_world": (
                [float(value) for value in data.xpos[controlled_root_id]]
                if controlled_root_id is not None
                else None
            ),
            "minimum_root_height": min_root_height,
            "policy_control": headless_controller is not None,
        },
        "policy": policy_result,
        "policy_runtime": (
            {
                "inference_steps": int(headless_controller.policy_step),
                "legacy_angular_velocity_sensor_reads": int(headless_controller.legacy_angular_velocity_sensor_reads),
                "first_observation": [float(value) for value in headless_controller.first_observation],
                "first_observation_head": [float(value) for value in headless_controller.first_observation[:55]],
                "first_action": [float(value) for value in headless_controller.first_action],
            }
            if headless_controller is not None
            and headless_controller.first_observation is not None
            and headless_controller.first_action is not None
            else None
        ),
        "render": str(args.render.resolve()) if args.render else None,
        "python": sys.version,
        "mujoco": mujoco.__version__,
    }
    report_path = args.report.resolve() if args.report else root / "sim2sim" / "sim2sim_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.viewer:
        reset_model(mujoco, model, data, profile, keyframe_qpos_lengths)
        launch_viewer(
            mujoco,
            model,
            data,
            root,
            manifest,
            profile,
            args.viewer_seconds,
            args.command_vx,
            not args.no_policy_control,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"LOCAL_MUJOCO_FAILED: {error}", file=sys.stderr)
        raise
