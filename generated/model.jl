using SparseArrays
using NLsolve
using LinearAlgebra
using JSON

_DATA = JSON.parsefile(joinpath(@__DIR__, "model_data.json"))

function _mx(n)
    e = _DATA["matrices"][n]
    return sparse(Int.(e["i"]) .+ 1, Int.(e["j"]) .+ 1, Float64.(e["v"]), e["m"], e["n"])
end

function _shape(e)
    d = Int.(e["dims"])
    length(d) <= 1 && return Float64.(e["flat"])
    # C-order flat → column-major: reshape the     # reversed dims, permute back
    return permutedims(reshape(Float64.(e["flat"]),         reverse(d)...), reverse(1:length(d)))
end

_tab(n) = _shape(_DATA["values"][n])

_ictab(n) = _shape(_DATA["ics"][n])

F_conv_convection_transport = _mx("F_conv_convection_transport")  # F over [1 x 2]
F_conv_lumped = _mx("F_conv_lumped")  # F over [1 x 1]

function derivative!(dy, y, par, t; outs=nothing)
    V_57_lumped = @view y[1:1]
    V_39 = _tab("V_39")  # value cells
    V_54 = _tab("V_54")  # value cells
    V_57_convection_transport = _tab("V_57_convection_transport")  # value cells
    V_34_environment = _tab("V_34_environment")  # value cells
    V_34_lumped = _tab("V_34_lumped")  # value cells
    V_34_convection_transport = vcat(V_34_environment[[1]], V_34_lumped[[1]])  # port gather
    function _balance(u)
        V_56_convection_transport = u[1:2]
        dV_57_lumped = u[3:3]
        V_56_lumped = V_56_convection_transport[[2]]  # port gather
        _r0 = vec((reshape(( ( V_39 .* V_54 ) .* ( contract(V_34_convection_transport, F_conv_convection_transport, (1,), (1,)) ) ), (1, 1))) .- V_56_convection_transport)
        _r1 = vec((reshape(dropdims(sum(( F_conv_lumped .* V_56_lumped ), dims=1), dims=1), (1, 1))) .- dV_57_lumped)
        _r2 = vec((reshape(dropdims(sum(( F_conv_convection_transport .* V_56_convection_transport ), dims=1), dims=1), (1, 1))) .- V_57_convection_transport)
        return vcat(_r0, _r1, _r2)
    end
    _u = _solve_balance(_balance, 3, :balance)
    V_56_convection_transport = _u[1:2]
    dV_57_lumped = _u[3:3]
    dy[1:1] = vec(dV_57_lumped)
    if outs !== nothing  # §21 outputs
        outs[:V_56_convection_transport] = V_56_convection_transport
    end
    return nothing
end

function outputs(y, par, t)
    outs = Dict{Symbol,Any}()
    derivative!(zeros(length(y)), y, par, t; outs=outs)
    return outs
end

function initial(par; steady_state=false)
    V_39 = _tab("V_39")  # value cells
    V_54 = _tab("V_54")  # value cells
    V_57_convection_transport = _tab("V_57_convection_transport")  # value cells
    V_34_environment = _tab("V_34_environment")  # value cells
    V_34_lumped = _tab("V_34_lumped")  # value cells
    V_34_convection_transport = vcat(V_34_environment[[1]], V_34_lumped[[1]])  # port gather
    function _t0(u)  # t=0 residual system
        V_57_lumped = u[1:1]
        V_56_convection_transport = u[2:3]
        dV_57_lumped = u[4:4]
        if steady_state
            total_diff = (x, y) -> x .* 0  # der = 0
        end
        V_56_lumped = V_56_convection_transport[[2]]  # port gather
        _r0 = vec((reshape(( ( V_39 .* V_54 ) .* ( contract(V_34_convection_transport, F_conv_convection_transport, (1,), (1,)) ) ), (1, 1))) .- V_56_convection_transport)
        _r1 = vec((reshape(dropdims(sum(( F_conv_lumped .* V_56_lumped ), dims=1), dims=1), (1, 1))) .- dV_57_lumped)
        _r2 = vec((reshape(dropdims(sum(( F_conv_convection_transport .* V_56_convection_transport ), dims=1), dims=1), (1, 1))) .- V_57_convection_transport)
        _rs = Any[_r0, _r1, _r2]
        if steady_state
            append!(_rs, Any[vec(dV_57_lumped)])  # der = 0
        else
            _e0 = vec((_ictab("V_57_lumped")) .- V_57_lumped)  # IC pin
            append!(_rs, Any[_e0])
        end
        return isempty(_rs) ? zeros(length(u)) : vcat(_rs...)
    end
    _u = _solve_balance(_t0, 4, (:t0, steady_state))
    V_57_lumped = _u[1:1]
    return vcat(V_57_lumped)
end

function contract(a, b, da, db)
    ca = collect(da); cb = collect(db)
    fa = setdiff(collect(1:ndims(a)), ca)
    fb = setdiff(collect(1:ndims(b)), cb)
    A = reshape(permutedims(a, vcat(fa, ca)), :,
                prod(size(a)[ca]))
    B = reshape(permutedims(b, vcat(cb, fb)),
                prod(size(b)[cb]), :)
    dims = (size(a)[fa]..., size(b)[fb]...)
    return isempty(dims) ? A * B : reshape(A * B, dims)
end
const _BAL_CACHE = Dict{Any, Any}()
function _solve_balance(fun, count, key)
    if count == 0
        u = zeros(0); r = fun(u)
        (all(isfinite, r) && all(abs.(r) .<= 1e-8)) || error("inconsistent prescribed balance")
        return u
    end
    cached = get(_BAL_CACHE, key, nothing)
    cached === :nonlin && return _nlsolve_balance(fun, count)
    r0 = fun(zeros(count))
    n = length(r0)
    if cached === nothing
        cached = zeros(n, count)
        for k in 1:count
            ek = zeros(count); ek[k] = 1.0
            cached[:, k] = fun(ek) .- r0
        end
        _BAL_CACHE[key] = cached
    end
    A = cached
    if rank(A) >= count
        u = -(A \ r0)
        r = fun(u)
        (all(isfinite, r) && all(abs.(r) .<= 1e-8)) && return u
    else
        error("prescribed balance system is underdetermined")
    end
    n == count || error("prescribed balance: nonlinear overdetermined system — unsupported")
    _BAL_CACHE[key] = :nonlin
    return _nlsolve_balance(fun, count)
end

function _nlsolve_balance(fun, count)
    res = nlsolve(fun, zeros(count))
    r = fun(res.zero)
    (NLsolve.converged(res) && all(isfinite, r) && all(abs.(r) .<= 1e-8)) || error("prescribed balance solve failed")
    return res.zero
end