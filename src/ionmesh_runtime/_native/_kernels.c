#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>

typedef struct {
    double energy;
    double weight;
} item_t;

static int cmp_desc_energy(const void *lhs, const void *rhs) {
    const item_t *a = (const item_t *)lhs;
    const item_t *b = (const item_t *)rhs;
    if (a->energy < b->energy) return 1;
    if (a->energy > b->energy) return -1;
    return 0;
}

static int read_double_buffer(PyObject *obj, Py_buffer *view) {
    if (PyObject_GetBuffer(obj, view, PyBUF_CONTIG_RO | PyBUF_FORMAT) != 0) {
        return -1;
    }
    if (view->itemsize != (Py_ssize_t)sizeof(double)) {
        PyErr_SetString(PyExc_TypeError, "expected float64 buffer");
        PyBuffer_Release(view);
        return -1;
    }
    return 0;
}

static int read_u8_buffer(PyObject *obj, Py_buffer *view) {
    if (PyObject_GetBuffer(obj, view, PyBUF_CONTIG_RO | PyBUF_FORMAT) != 0) {
        return -1;
    }
    if (view->itemsize != (Py_ssize_t)sizeof(uint8_t)) {
        PyErr_SetString(PyExc_TypeError, "expected uint8 buffer");
        PyBuffer_Release(view);
        return -1;
    }
    return 0;
}

static PyObject *weighted_cvar(PyObject *self, PyObject *args) {
    PyObject *energies_obj = NULL;
    PyObject *weights_obj = NULL;
    double alpha = 0.0;
    Py_buffer ebuf = {0};
    Py_buffer wbuf = {0};
    item_t *items = NULL;
    if (!PyArg_ParseTuple(args, "OOd", &energies_obj, &weights_obj, &alpha)) {
        return NULL;
    }
    if (read_double_buffer(energies_obj, &ebuf) != 0) return NULL;
    if (read_double_buffer(weights_obj, &wbuf) != 0) {
        PyBuffer_Release(&ebuf);
        return NULL;
    }
    Py_ssize_t n = ebuf.len / (Py_ssize_t)sizeof(double);
    if (wbuf.len != ebuf.len) {
        PyBuffer_Release(&ebuf);
        PyBuffer_Release(&wbuf);
        PyErr_SetString(PyExc_ValueError, "mismatched lengths");
        return NULL;
    }
    if (n <= 0) {
        PyBuffer_Release(&ebuf);
        PyBuffer_Release(&wbuf);
        return Py_BuildValue("(ddd)", 1e9, 1.0, 1e9);
    }
    items = (item_t *)PyMem_Malloc((size_t)n * sizeof(item_t));
    if (items == NULL) {
        PyBuffer_Release(&ebuf);
        PyBuffer_Release(&wbuf);
        return PyErr_NoMemory();
    }
    double *energies = (double *)ebuf.buf;
    double *weights = (double *)wbuf.buf;
    double total = 0.0;
    double feasible_best = DBL_MAX;
    for (Py_ssize_t i = 0; i < n; ++i) {
        items[i].energy = energies[i];
        items[i].weight = weights[i];
        total += weights[i];
        if (energies[i] < feasible_best) feasible_best = energies[i];
    }
    if (total <= 0.0) {
        PyMem_Free(items);
        PyBuffer_Release(&ebuf);
        PyBuffer_Release(&wbuf);
        return Py_BuildValue("(ddd)", 1e9, 1.0, 1e9);
    }
    qsort(items, (size_t)n, sizeof(item_t), cmp_desc_energy);
    double target = alpha * total;
    if (target < 1e-12) target = 1e-12;
    double cumulative = 0.0;
    double sum1 = 0.0;
    double sum2 = 0.0;
    for (Py_ssize_t i = 0; i < n; ++i) {
        double remaining = target - cumulative;
        if (remaining <= 0.0) break;
        double share = items[i].weight < remaining ? items[i].weight : remaining;
        if (share <= 0.0) continue;
        cumulative += share;
        sum1 += items[i].energy * share;
        sum2 += items[i].energy * items[i].energy * share;
        if (cumulative >= target) break;
    }
    double denom = cumulative > 1e-12 ? cumulative : 1e-12;
    double mean = sum1 / denom;
    double second = sum2 / denom;
    double variance = second - mean * mean;
    if (variance < 1e-12) variance = 1e-12;
    PyMem_Free(items);
    PyBuffer_Release(&ebuf);
    PyBuffer_Release(&wbuf);
    return Py_BuildValue("(ddd)", mean, variance, feasible_best);
}

static PyObject *distribution_stats(PyObject *self, PyObject *args) {
    PyObject *base_obj = NULL;
    PyObject *weights_obj = NULL;
    PyObject *valid_obj = NULL;
    PyObject *success_obj = NULL;
    Py_buffer bbuf = {0};
    Py_buffer wbuf = {0};
    Py_buffer vbuf = {0};
    Py_buffer sbuf = {0};
    if (!PyArg_ParseTuple(args, "OOOO", &base_obj, &weights_obj, &valid_obj, &success_obj)) {
        return NULL;
    }
    if (read_double_buffer(base_obj, &bbuf) != 0) return NULL;
    if (read_double_buffer(weights_obj, &wbuf) != 0) { PyBuffer_Release(&bbuf); return NULL; }
    if (read_u8_buffer(valid_obj, &vbuf) != 0) { PyBuffer_Release(&bbuf); PyBuffer_Release(&wbuf); return NULL; }
    if (read_u8_buffer(success_obj, &sbuf) != 0) { PyBuffer_Release(&bbuf); PyBuffer_Release(&wbuf); PyBuffer_Release(&vbuf); return NULL; }
    Py_ssize_t n = bbuf.len / (Py_ssize_t)sizeof(double);
    if (wbuf.len != bbuf.len || vbuf.len != (Py_ssize_t)n || sbuf.len != (Py_ssize_t)n) {
        PyBuffer_Release(&bbuf); PyBuffer_Release(&wbuf); PyBuffer_Release(&vbuf); PyBuffer_Release(&sbuf);
        PyErr_SetString(PyExc_ValueError, "mismatched lengths");
        return NULL;
    }
    double *base = (double *)bbuf.buf;
    double *weights = (double *)wbuf.buf;
    uint8_t *valid = (uint8_t *)vbuf.buf;
    uint8_t *success = (uint8_t *)sbuf.buf;
    double total = 0.0;
    double valid_weight = 0.0;
    double success_weight = 0.0;
    double raw_best = DBL_MAX;
    double feasible_best = DBL_MAX;
    int saw_raw = 0;
    int saw_feasible = 0;
    for (Py_ssize_t i = 0; i < n; ++i) {
        double w = weights[i];
        total += w;
        if (w <= 0.0) continue;
        saw_raw = 1;
        if (base[i] < raw_best) raw_best = base[i];
        if (valid[i]) {
            valid_weight += w;
            if (base[i] < feasible_best) feasible_best = base[i];
            saw_feasible = 1;
        }
        if (success[i]) success_weight += w;
    }
    if (!saw_raw) raw_best = 1e9;
    if (!saw_feasible) feasible_best = 1e9;
    PyBuffer_Release(&bbuf); PyBuffer_Release(&wbuf); PyBuffer_Release(&vbuf); PyBuffer_Release(&sbuf);
    return Py_BuildValue("(ddddd)", raw_best, feasible_best, valid_weight, success_weight, total);
}

static PyMethodDef Methods[] = {
    {"weighted_cvar", weighted_cvar, METH_VARARGS, ""},
    {"distribution_stats", distribution_stats, METH_VARARGS, ""},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_kernels",
    NULL,
    -1,
    Methods,
};

PyMODINIT_FUNC PyInit__kernels(void) {
    return PyModule_Create(&moduledef);
}
