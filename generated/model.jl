using SparseArrays

V_25_convection_transport = sparse([1, 1], [1, 2], [1, -1], 1, 2)  # F over [1 x 2]
V_25_lumped = sparse([1], [1], [1], 1, 1)  # F over [1 x 1]

function derivative!(dy, y, par, t)
    V_31_convection_transport = @view y[1:2]
    V_6 = @view y[3:3]
    V_17_convection_transport = par.V_17_convection_transport
    V_13_convection_transport = par.V_13_convection_transport
    V_29_convection_transport = par.V_29_convection_transport
    V_10_environment = par.V_10_environment
    V_24_environment = par.V_24_environment
    V_10_lumped = par.V_10_lumped
    V_17_lumped = par.V_17_lumped
    V_13_lumped = par.V_13_lumped
    V_29_lumped = par.V_29_lumped
    V_11 = par.V_11
    V_22 = par.V_22
    V_21 = par.V_21
    # level 0
    V_10_convection_transport = V_10_environment[[1, 0]]  # port gather
    V_26_convection_transport = sign.(( V_25_convection_transport * V_10_convection_transport ))
    V_30_convection_transport = ( ( ( ( 1 ./ V_29_convection_transport .* V_13_convection_transport ) .* V_17_convection_transport ) .* V_25_convection_transport ) .* V_10_convection_transport )
    V_26_lumped = sign.(( V_25_lumped * V_10_lumped ))
    V_30_lumped = ( ( ( ( 1 ./ V_29_lumped .* V_13_lumped ) .* V_17_lumped ) .* V_25_lumped ) .* V_10_lumped )
    # level 1
    V_24_convection_transport = V_24_environment[[1, 1]]  # port gather
    V_24_lumped = V_24_environment[[1]]  # port gather
    V_27_convection_transport = ( contract(( 0.5 .* ( V_25_convection_transport - ( V_26_convection_transport .* abs.(V_25_convection_transport) ) ) ), V_24_convection_transport, (2,), (1,)) )
    V_27_lumped = ( contract(( 0.5 .* ( V_25_lumped - ( V_26_lumped .* abs.(V_25_lumped) ) ) ), V_24_lumped, (2,), (1,)) )
    # level 2
    dy[1:2] = ( V_27_convection_transport .* V_30_convection_transport )
    V_31_lumped = ( V_27_lumped .* V_30_lumped )
    # level 3
    V_32 = ( V_25_lumped .* V_31_lumped )
    # level 4
    V_33 = V_32
    # level 5
    dy[3:3] = quadgk(V_11 -> V_33, V_21, V_22)[1]
    return nothing
end

function initial(par; steady_state=false)
    V_17_convection_transport = par.V_17_convection_transport
    V_13_convection_transport = par.V_13_convection_transport
    V_29_convection_transport = par.V_29_convection_transport
    V_10_environment = par.V_10_environment
    V_24_environment = par.V_24_environment
    V_10_lumped = par.V_10_lumped
    V_17_lumped = par.V_17_lumped
    V_13_lumped = par.V_13_lumped
    V_29_lumped = par.V_29_lumped
    V_11 = par.V_11
    V_22 = par.V_22
    V_21 = par.V_21
    function _t0(u)  # t=0 residual system
        V_31_convection_transport = u[1:2]
        V_6 = u[3:3]
        V_26_convection_transport = u[4:5]
        V_30_convection_transport = u[6:7]
        V_26_lumped = u[8:8]
        V_30_lumped = u[9:9]
        V_27_convection_transport = u[10:11]
        V_27_lumped = u[12:12]
        V_31_lumped = u[13:13]
        V_32 = u[14:14]
        V_33 = u[15:15]
        dV_31_convection_transport = u[16:17]
        dV_6 = u[18:18]
        if steady_state
            total_diff = (x, y) -> x .* 0  # der = 0
        end
        V_10_convection_transport = V_10_environment[[1, 0]]  # port gather
        V_24_convection_transport = V_24_environment[[1, 1]]  # port gather
        V_24_lumped = V_24_environment[[1]]  # port gather
        _r0 = (sign.(( V_25_convection_transport * V_10_convection_transport ))) .- V_26_convection_transport
        _r1 = (( ( ( ( 1 ./ V_29_convection_transport .* V_13_convection_transport ) .* V_17_convection_transport ) .* V_25_convection_transport ) .* V_10_convection_transport )) .- V_30_convection_transport
        _r2 = (sign.(( V_25_lumped * V_10_lumped ))) .- V_26_lumped
        _r3 = (( ( ( ( 1 ./ V_29_lumped .* V_13_lumped ) .* V_17_lumped ) .* V_25_lumped ) .* V_10_lumped )) .- V_30_lumped
        _r4 = (( contract(( 0.5 .* ( V_25_convection_transport - ( V_26_convection_transport .* abs.(V_25_convection_transport) ) ) ), V_24_convection_transport, (2,), (1,)) )) .- V_27_convection_transport
        _r5 = (( contract(( 0.5 .* ( V_25_lumped - ( V_26_lumped .* abs.(V_25_lumped) ) ) ), V_24_lumped, (2,), (1,)) )) .- V_27_lumped
        _r6 = (( V_27_convection_transport .* V_30_convection_transport )) .- dV_31_convection_transport
        _r7 = (( V_27_lumped .* V_30_lumped )) .- V_31_lumped
        _r8 = (( V_25_lumped .* V_31_lumped )) .- V_32
        _r9 = (V_32) .- V_33
        _r10 = (quadgk(V_11 -> V_33, V_21, V_22)[1]) .- dV_6
        _rs = Any[_r0, _r1, _r2, _r3, _r4, _r5, _r6, _r7, _r8, _r9, _r10]
        if steady_state
            append!(_rs, Any[dV_31_convection_transport, dV_6])  # der = 0
        else
            _e0 = (par.ic0_V_31_convection_transport) .- V_31_convection_transport  # IC pin
            _e1 = (par.ic0_V_6) .- V_6  # IC pin
            append!(_rs, Any[_e0, _e1])
        end
        return isempty(_rs) ? zeros(length(u)) : vcat(_rs...)
    end
    _u = nlsolve(_t0, zeros(18)).zero
    V_31_convection_transport = _u[1:2]
    V_6 = _u[3:3]
    return [V_31_convection_transport; V_6]
end
