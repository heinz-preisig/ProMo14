V_25_convection_transport = MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, sparse([1; 1], [1; 2], [1; -1], 1, 2));  % F over [1 x 2]
V_25_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, sparse([1], [1], [1], 1, 1));  % F over [1 x 1]

function dy = derivative(t, y, par)
  dy = zeros(3, 1);
  V_31_convection_transport = MultiDimVar({'A_conv', 'N', 'S'}, [2 1 1], {'A_conv', 'N', 'S'}, y(1:2));
  V_6 = MultiDimVar({'N', 'S', 'A_conv'}, [1 1 1], {'N', 'S', 'A_conv'}, y(3:3));
  V_17_convection_transport = MultiDimVar({'N'}, 1, {'N'}, par.V_17_convection_transport);
  V_13_convection_transport = MultiDimVar({'N'}, 1, {'N'}, par.V_13_convection_transport);
  V_29_convection_transport = MultiDimVar({'N'}, 1, {'N'}, par.V_29_convection_transport);
  V_10_environment = MultiDimVar({'N'}, 1, {'N'}, par.V_10_environment);
  V_24_environment = MultiDimVar({'N', 'S'}, [1 1], {'N', 'S'}, par.V_24_environment);
  V_10_lumped = MultiDimVar({'N'}, 1, {'N'}, par.V_10_lumped);
  V_17_lumped = MultiDimVar({'N'}, 1, {'N'}, par.V_17_lumped);
  V_13_lumped = MultiDimVar({'N'}, 1, {'N'}, par.V_13_lumped);
  V_29_lumped = MultiDimVar({'N'}, 1, {'N'}, par.V_29_lumped);
  V_11 = MultiDimVar({}, 1, {}, par.V_11);
  V_22 = MultiDimVar({}, 1, {}, par.V_22);
  V_21 = MultiDimVar({}, 1, {}, par.V_21);
  % level 0
  V_10_convection_transport = MultiDimVar({'N'}, 1, {'N'}, V_10_environment.value([1 0]));  % port gather
  V_26_convection_transport = sign(( einsum(V_25_convection_transport, V_10_convection_transport, {'N'}) ));
  V_30_convection_transport = ( einsum(( einsum(( einsum(( einsum(1 ./ V_29_convection_transport, V_13_convection_transport) ), V_17_convection_transport) ), V_25_convection_transport) ), V_10_convection_transport) );
  V_26_lumped = sign(( einsum(V_25_lumped, V_10_lumped, {'N'}) ));
  V_30_lumped = ( einsum(( einsum(( einsum(( einsum(1 ./ V_29_lumped, V_13_lumped) ), V_17_lumped) ), V_25_lumped) ), V_10_lumped) );
  % level 1
  V_24_convection_transport = MultiDimVar({'N', 'S'}, [1 1], {'N', 'S'}, V_24_environment.value([1 1]));  % port gather
  V_24_lumped = MultiDimVar({'N', 'S'}, [1 1], {'N', 'S'}, V_24_environment.value([1]));  % port gather
  V_27_convection_transport = ( einsum(( einsum(0.5, ( V_25_convection_transport - ( einsum(V_26_convection_transport, abs(V_25_convection_transport)) ) )) ), V_24_convection_transport, {'N'}) );
  V_27_lumped = ( einsum(( einsum(0.5, ( V_25_lumped - ( einsum(V_26_lumped, abs(V_25_lumped)) ) )) ), V_24_lumped, {'N'}) );
  % level 2
  dV_31_convection_transport = ( einsum(V_27_convection_transport, V_30_convection_transport) );
  dy(1:2) = dV_31_convection_transport.value;
  V_31_lumped = ( einsum(V_27_lumped, V_30_lumped) );
  % level 3
  V_32 = ( einsum(V_25_lumped, V_31_lumped) );
  % level 4
  V_33 = V_32;
  % level 5
  dV_6 = integral(@(V_11) _mdv_value(V_33), V_21, V_22, 'ArrayValued', true);
  dy(3:3) = dV_6.value;
end

function y0 = initial(par, steady_state)
  V_17_convection_transport = MultiDimVar({'N'}, 1, {'N'}, par.V_17_convection_transport);
  V_13_convection_transport = MultiDimVar({'N'}, 1, {'N'}, par.V_13_convection_transport);
  V_29_convection_transport = MultiDimVar({'N'}, 1, {'N'}, par.V_29_convection_transport);
  V_10_environment = MultiDimVar({'N'}, 1, {'N'}, par.V_10_environment);
  V_24_environment = MultiDimVar({'N', 'S'}, [1 1], {'N', 'S'}, par.V_24_environment);
  V_10_lumped = MultiDimVar({'N'}, 1, {'N'}, par.V_10_lumped);
  V_17_lumped = MultiDimVar({'N'}, 1, {'N'}, par.V_17_lumped);
  V_13_lumped = MultiDimVar({'N'}, 1, {'N'}, par.V_13_lumped);
  V_29_lumped = MultiDimVar({'N'}, 1, {'N'}, par.V_29_lumped);
  V_11 = MultiDimVar({}, 1, {}, par.V_11);
  V_22 = MultiDimVar({}, 1, {}, par.V_22);
  V_21 = MultiDimVar({}, 1, {}, par.V_21);
  function r = _t0(u)  %% t=0 residual system
    V_31_convection_transport = MultiDimVar({'A_conv', 'N', 'S'}, [2 1 1], {'A_conv', 'N', 'S'}, u(1:2));
    V_6 = MultiDimVar({'N', 'S', 'A_conv'}, [1 1 1], {'N', 'S', 'A_conv'}, u(3:3));
    V_26_convection_transport = MultiDimVar({'A_conv'}, 2, {'A_conv'}, u(4:5));
    V_30_convection_transport = MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, u(6:7));
    V_26_lumped = MultiDimVar({'A_conv'}, 1, {'A_conv'}, u(8:8));
    V_30_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, u(9:9));
    V_27_convection_transport = MultiDimVar({'A_conv', 'S'}, [2 1], {'A_conv', 'S'}, u(10:11));
    V_27_lumped = MultiDimVar({'A_conv', 'S'}, [1 1], {'A_conv', 'S'}, u(12:12));
    V_31_lumped = MultiDimVar({'A_conv', 'N', 'S'}, [1 1 1], {'A_conv', 'N', 'S'}, u(13:13));
    V_32 = MultiDimVar({'A_conv', 'N', 'S'}, [1 1 1], {'A_conv', 'N', 'S'}, u(14:14));
    V_33 = MultiDimVar({'A_conv', 'N', 'S'}, [1 1 1], {'A_conv', 'N', 'S'}, u(15:15));
    dV_31_convection_transport = MultiDimVar({'A_conv', 'N', 'S'}, [2 1 1], {'A_conv', 'N', 'S'}, u(16:17));
    dV_6 = MultiDimVar({'N', 'S', 'A_conv'}, [1 1 1], {'N', 'S', 'A_conv'}, u(18:18));
    if steady_state
      totalDiff = @(x, y) x .* 0;  %% der = 0
    end
    V_10_convection_transport = MultiDimVar({'N'}, 1, {'N'}, V_10_environment.value([1 0]));  % port gather
    V_24_convection_transport = MultiDimVar({'N', 'S'}, [1 1], {'N', 'S'}, V_24_environment.value([1 1]));  % port gather
    V_24_lumped = MultiDimVar({'N', 'S'}, [1 1], {'N', 'S'}, V_24_environment.value([1]));  % port gather
    _r0 = (sign(( einsum(V_25_convection_transport, V_10_convection_transport, {'N'}) ))) - V_26_convection_transport;
    _r1 = (( einsum(( einsum(( einsum(( einsum(1 ./ V_29_convection_transport, V_13_convection_transport) ), V_17_convection_transport) ), V_25_convection_transport) ), V_10_convection_transport) )) - V_30_convection_transport;
    _r2 = (sign(( einsum(V_25_lumped, V_10_lumped, {'N'}) ))) - V_26_lumped;
    _r3 = (( einsum(( einsum(( einsum(( einsum(1 ./ V_29_lumped, V_13_lumped) ), V_17_lumped) ), V_25_lumped) ), V_10_lumped) )) - V_30_lumped;
    _r4 = (( einsum(( einsum(0.5, ( V_25_convection_transport - ( einsum(V_26_convection_transport, abs(V_25_convection_transport)) ) )) ), V_24_convection_transport, {'N'}) )) - V_27_convection_transport;
    _r5 = (( einsum(( einsum(0.5, ( V_25_lumped - ( einsum(V_26_lumped, abs(V_25_lumped)) ) )) ), V_24_lumped, {'N'}) )) - V_27_lumped;
    _r6 = (( einsum(V_27_convection_transport, V_30_convection_transport) )) - dV_31_convection_transport;
    _r7 = (( einsum(V_27_lumped, V_30_lumped) )) - V_31_lumped;
    _r8 = (( einsum(V_25_lumped, V_31_lumped) )) - V_32;
    _r9 = (V_32) - V_33;
    _r10 = (integral(@(V_11) _mdv_value(V_33), V_21, V_22, 'ArrayValued', true)) - dV_6;
    r = [_r0.value; _r1.value; _r2.value; _r3.value; _r4.value; _r5.value; _r6.value; _r7.value; _r8.value; _r9.value; _r10.value];
    if steady_state
      r = [r; dV_31_convection_transport.value; dV_6.value];  % der = 0
    else
      _e0 = (MultiDimVar({'A_conv', 'N', 'S'}, [2 1 1], {'A_conv', 'N', 'S'}, par.ic0_V_31_convection_transport)) - V_31_convection_transport;  % IC pin
      _e1 = (MultiDimVar({'N', 'S', 'A_conv'}, [1 1 1], {'N', 'S', 'A_conv'}, par.ic0_V_6)) - V_6;  % IC pin
      r = [r; _e0.value; _e1.value];
    end
  end
  _u = fsolve(@_t0, zeros(18, 1));
  V_31_convection_transport = MultiDimVar({'A_conv', 'N', 'S'}, [2 1 1], {'A_conv', 'N', 'S'}, _u(1:2));
  V_6 = MultiDimVar({'N', 'S', 'A_conv'}, [1 1 1], {'N', 'S', 'A_conv'}, _u(3:3));
  y0 = [V_31_convection_transport.value(:); V_6.value(:)];
end


function v = _mdv_value(x)
  if isa(x, 'MultiDimVar'), x = x.value; end
  v = x;
end