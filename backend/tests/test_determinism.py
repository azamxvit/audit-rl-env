"""Replays: same seed + config + version + actions => identical records, transitions, rewards, trajectories."""
import hashlib

from audit_env.env import AuditEnv
from audit_env.policies import FlagAllPolicy, RandomExplorerPolicy, SimpleReconcilerPolicy
from audit_env.trajectories import TrajectoryWriter, run_episode

from conftest import cfg


def _traj_hash(tmp_path, tag, policy_factory, seed, config):
    path = tmp_path / f"{tag}.jsonl"
    env = AuditEnv("train")
    with TrajectoryWriter(path) as w:
        run_episode(env, policy_factory(), seed=seed, config=config, writer=w)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_trajectories_bit_identical(tmp_path):
    for seed, config in [(3, None), (1005, cfg("train/interacting.json"))]:
        for name, factory in [("rnd", lambda: RandomExplorerPolicy(7)), ("rec", SimpleReconcilerPolicy),
                              ("all", FlagAllPolicy)]:
            assert _traj_hash(tmp_path, f"{name}a", factory, seed, config) == \
                _traj_hash(tmp_path, f"{name}b", factory, seed, config)


def test_replaying_recorded_actions_reproduces_transitions():
    env = AuditEnv("train")
    obs, _ = env.reset(seed=8)
    pol = RandomExplorerPolicy(3)
    pol.reset(obs)
    actions, transitions = [], []
    done = False
    while not done:
        a = pol.act(obs)
        out = env.step(a)
        obs = out[0]
        actions.append(a)
        transitions.append(out)
        done = out[2] or out[3]
    env2 = AuditEnv("train")
    env2.reset(seed=8)
    assert [env2.step(a) for a in actions] == transitions


def test_generation_independent_of_hash_seed():
    import subprocess, sys, os
    code = ("from audit_env.generator import generate_episode, public_files;"
            "from audit_env.util import sha256_text;"
            "print(sha256_text(''.join(public_files(generate_episode(5).public).values())))")
    outs = set()
    for hs in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hs, PYTHONPATH="src")
        outs.add(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                                check=True).stdout)
    assert len(outs) == 1
