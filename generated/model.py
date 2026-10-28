import numpy as np
import scipy.sparse
import scipy.optimize
from scipy.optimize import fsolve
import json as _json
import os.path as _osp

_DIR = (_osp.dirname(_osp.abspath(__file__)) if '__file__' in globals() else '')
if '_DATA' not in globals():
    _DATA = _json.load(open(_osp.join(_DIR, "model_data.json")))

def _mx(n):
    e = _DATA['matrices'][n]
    return scipy.sparse.coo_array(        (e['v'], (e['i'], e['j'])),        shape=(e['m'], e['n']))

V_25_convection_transport = _mx("V_25_convection_transport")  # F over [1 x 2]
V_25_lumped = _mx("V_25_lumped")  # F over [1 x 1]

def derivative(t, y, par):
    dy = np.zeros(3)
    V_31_convection_transport = y[0:2]
    V_6 = y[2:3]
    V_17_convection_transport = par["V_17_convection_transport"]
    V_13_convection_transport = par["V_13_convection_transport"]
    V_29_convection_transport = par["V_29_convection_transport"]
    V_10_environment = par["V_10_environment"]
    V_24_environment = par["V_24_environment"]
    V_10_lumped = par["V_10_lumped"]
    V_17_lumped = par["V_17_lumped"]
    V_13_lumped = par["V_13_lumped"]
    V_29_lumped = par["V_29_lumped"]
    V_11 = par["V_11"]
    V_22 = par["V_22"]
    V_21 = par["V_21"]
    # level 0
    V_10_convection_transport = V_10_environment[[0, -1]]  # port gather
    V_26_convection_transport = np.sign(( V_25_convection_transport @ V_10_convection_transport ))
    V_30_convection_transport = ( ( V_25_convection_transport.multiply(np.asarray(( ( 1 / V_29_convection_transport * V_13_convection_transport ) * V_17_convection_transport ))) ).multiply(np.asarray(V_10_convection_transport)) )
    V_26_lumped = np.sign(( V_25_lumped @ V_10_lumped ))
    V_30_lumped = ( ( V_25_lumped.multiply(np.asarray(( ( 1 / V_29_lumped * V_13_lumped ) * V_17_lumped ))) ).multiply(np.asarray(V_10_lumped)) )
    # level 1
    V_24_convection_transport = V_24_environment[[0, 0]]  # port gather
    V_24_lumped = V_24_environment[[0]]  # port gather
    V_27_convection_transport = ( ( ( V_25_convection_transport - ( np.abs(V_25_convection_transport).multiply(np.asarray(V_26_convection_transport)) ) ).multiply(np.asarray(0.5)) ) @ V_24_convection_transport )
    V_27_lumped = ( ( ( V_25_lumped - ( np.abs(V_25_lumped).multiply(np.asarray(V_26_lumped)) ) ).multiply(np.asarray(0.5)) ) @ V_24_lumped )
    # level 2
    dy[0:2] = _d(( V_30_convection_transport.multiply(np.asarray(V_27_convection_transport)) ))
    V_31_lumped = ( V_30_lumped.multiply(np.asarray(V_27_lumped)) )
    # level 3
    V_32 = ( V_25_lumped.multiply(V_31_lumped) )
    # level 4
    V_33 = V_32
    # level 5
    dy[2:3] = _d(scipy.integrate.quad_vec(lambda V_11: (V_33).toarray(), V_21, V_22)[0])
    return dy

def initial(par, steady_state=False):
    V_17_convection_transport = par["V_17_convection_transport"]
    V_13_convection_transport = par["V_13_convection_transport"]
    V_29_convection_transport = par["V_29_convection_transport"]
    V_10_environment = par["V_10_environment"]
    V_24_environment = par["V_24_environment"]
    V_10_lumped = par["V_10_lumped"]
    V_17_lumped = par["V_17_lumped"]
    V_13_lumped = par["V_13_lumped"]
    V_29_lumped = par["V_29_lumped"]
    V_11 = par["V_11"]
    V_22 = par["V_22"]
    V_21 = par["V_21"]
    def _t0(u):  # t=0 residual system
        V_31_convection_transport = u[0:2]
        V_6 = u[2:3]
        V_26_convection_transport = u[3:5]
        V_30_convection_transport = u[5:7]
        V_26_lumped = u[7:8]
        V_30_lumped = u[8:9]
        V_27_convection_transport = u[9:11]
        V_27_lumped = u[11:12]
        V_31_lumped = u[12:13]
        V_32 = u[13:14]
        V_33 = u[14:15]
        dV_31_convection_transport = u[15:17]
        dV_6 = u[17:18]
        if steady_state:
            total_diff = lambda x, y: np.zeros_like(x)  # der = 0
        V_10_convection_transport = V_10_environment[[0, -1]]  # port gather
        V_24_convection_transport = V_24_environment[[0, 0]]  # port gather
        V_24_lumped = V_24_environment[[0]]  # port gather
        _r0 = (_d(np.sign(( V_25_convection_transport @ V_10_convection_transport )))) - V_26_convection_transport
        _r1 = (_d(( ( V_25_convection_transport.multiply(np.asarray(( ( 1 / V_29_convection_transport * V_13_convection_transport ) * V_17_convection_transport ))) ).multiply(np.asarray(V_10_convection_transport)) ))) - V_30_convection_transport
        _r2 = (_d(np.sign(( V_25_lumped @ V_10_lumped )))) - V_26_lumped
        _r3 = (_d(( ( V_25_lumped.multiply(np.asarray(( ( 1 / V_29_lumped * V_13_lumped ) * V_17_lumped ))) ).multiply(np.asarray(V_10_lumped)) ))) - V_30_lumped
        _r4 = (_d(( ( ( V_25_convection_transport - ( np.abs(V_25_convection_transport).multiply(np.asarray(V_26_convection_transport)) ) ).multiply(np.asarray(0.5)) ) @ V_24_convection_transport ))) - V_27_convection_transport
        _r5 = (_d(( ( ( V_25_lumped - ( np.abs(V_25_lumped).multiply(np.asarray(V_26_lumped)) ) ).multiply(np.asarray(0.5)) ) @ V_24_lumped ))) - V_27_lumped
        _r6 = (_d(( V_30_convection_transport.multiply(np.asarray(V_27_convection_transport)) ))) - dV_31_convection_transport
        _r7 = (_d(( V_30_lumped.multiply(np.asarray(V_27_lumped)) ))) - V_31_lumped
        _r8 = (_d(( V_25_lumped.multiply(V_31_lumped) ))) - V_32
        _r9 = (_d(V_32)) - V_33
        _r10 = (_d(scipy.integrate.quad_vec(lambda V_11: (V_33).toarray(), V_21, V_22)[0])) - dV_6
        _rs = [np.atleast_1d(_r0), np.atleast_1d(_r1), np.atleast_1d(_r2), np.atleast_1d(_r3), np.atleast_1d(_r4), np.atleast_1d(_r5), np.atleast_1d(_r6), np.atleast_1d(_r7), np.atleast_1d(_r8), np.atleast_1d(_r9), np.atleast_1d(_r10)]
        if steady_state:
            _rs += [np.atleast_1d(dV_31_convection_transport), np.atleast_1d(dV_6)]  # der = 0
        else:
            _e0 = (par["ic0_V_31_convection_transport"]) - V_31_convection_transport  # IC pin
            _e1 = (par["ic0_V_6"]) - V_6  # IC pin
            _rs += [np.atleast_1d(_e0), np.atleast_1d(_e1)]
        return np.concatenate(_rs) if _rs else np.zeros_like(u)
    _u = fsolve(_t0, np.zeros(18))
    V_31_convection_transport = _u[0:2]
    V_6 = _u[2:3]
    return np.concatenate([np.atleast_1d(V_31_convection_transport), np.atleast_1d(V_6)])


def _d(x):
    return x.toarray() if scipy.sparse.issparse(x) else x