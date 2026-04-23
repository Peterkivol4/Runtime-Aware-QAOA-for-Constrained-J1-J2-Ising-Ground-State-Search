from __future__ import annotations

ENV_PREFIX = 'SPINMESH_'

DEFAULT_LOG_FILE_PATTERN = '{name}_{timestamp}.log'
DEFAULT_LOG_FORMAT = '%(asctime)s | %(levelname)s | %(message)s'
DEFAULT_CONSOLE_LOG_FORMAT = '%(levelname)s: %(message)s'

DEFAULT_NOISE_PROFILE = {
    't1_time': 50e3,
    't2_time': 70e3,
    'readout_p10': 0.01,
    'readout_p01': 0.03,
    'depol_error': 0.005,
}

DEFAULT_GENERIC_BACKEND = {
    'num_qubits': 7,
    'seed': 11,
    'coupling_map': [(0, 1), (1, 2), (1, 3), (3, 5), (2, 4), (4, 6)],
    'basis_gates': ['id', 'rz', 'sx', 'x', 'cx', 'measure'],
}

DEFAULT_SQLITE = {
    'timeout_seconds': 30.0,
    'busy_timeout_ms': 30000,
    'journal_mode': 'WAL',
    'synchronous': 'NORMAL',
}

DEFAULT_SMOKE_OVERRIDES = {
    'depth': 1,
    'fourier_modes': 1,
    'bo_iters': 3,
    'sobol_init_iters': 2,
    'random_search_iters': 3,
    'spsa_iters': 3,
    'base_shots': 32,
    'study_num_seeds': 2,
    'n_spins': 4,
    'magnetization_m': 0,
    'j2_coupling': 0.5,
    'lattice_type': 'j1j2_frustrated',
}

DEFAULT_MARKET_TEMPLATE = {
    'periods': 260,
    'seed': 42,
}

DEFAULT_BOOTSTRAP = {
    'seed': 1234,
}

DEFAULT_RUNTIME_MESSAGES = {
    'runtime_unavailable': 'Runtime V2 support is unavailable. Install the runtime extra or use a non-runtime mode.',
    'missing_credentials': 'Runtime credentials are missing from the environment.',
    'tracker_schema_mismatch': 'tracker store schema mismatch; recreate or migrate the tracker store before continuing',
}

RUNTIME_SECRET_ENV = {
    'channel': ('QISKIT_IBM_CHANNEL', 'IBM_QUANTUM_CHANNEL'),
    'token': ('QISKIT_IBM_TOKEN', 'QISKIT_IBM_API_TOKEN', 'IBM_QUANTUM_TOKEN'),
    'instance': ('QISKIT_IBM_INSTANCE', 'IBM_QUANTUM_INSTANCE'),
    'url': ('QISKIT_IBM_URL', 'IBM_QUANTUM_URL'),
}

__all__ = [
    'ENV_PREFIX',
    'DEFAULT_LOG_FILE_PATTERN',
    'DEFAULT_LOG_FORMAT',
    'DEFAULT_CONSOLE_LOG_FORMAT',
    'DEFAULT_NOISE_PROFILE',
    'DEFAULT_GENERIC_BACKEND',
    'DEFAULT_SQLITE',
    'DEFAULT_SMOKE_OVERRIDES',
    'DEFAULT_MARKET_TEMPLATE',
    'DEFAULT_BOOTSTRAP',
    'DEFAULT_RUNTIME_MESSAGES',
    'RUNTIME_SECRET_ENV',
]
