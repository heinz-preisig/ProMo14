% ProMo-generated model file.  Companions required:
%   model_data.json — /code?target=data output, place next to this file
%   @MultiDimVar    — vendored Einstein-notation library,
%                     addpath('<repo>/runtime/matlab')
function [result, outs] = model(varargin)
  outs = struct();
F_conv_convection_transport = MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, full(promo_mx("F_conv_convection_transport")));  % F over [1 x 2]
F_conv_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, full(promo_mx("F_conv_lumped")));  % F over [1 x 1]


  V_39 = MultiDimVar({'N'}, 1, {'N'}, promo_tab("V_39"));  % bound once
  V_54 = MultiDimVar({'N'}, 1, {'N'}, promo_tab("V_54"));  % bound once
  V_57_convection_transport = MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, promo_tab("V_57_convection_transport"));  % bound once
  V_34_environment = MultiDimVar({'N'}, 1, {'N'}, promo_tab("V_34_environment"));  % bound once
  V_34_lumped = MultiDimVar({'N'}, 1, {'N'}, promo_tab("V_34_lumped"));  % bound once
  V_34_convection_transport = MultiDimVar({'A_conv'}, 2, {'A_conv'}, vertcat(V_34_environment.value([1]), V_34_lumped.value([1])));  % bound once
  promo_k1 = MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, repmat(reshape((( einsum(( einsum(V_39, V_54) ), ( einsum(V_34_convection_transport, F_conv_convection_transport, {'A_conv'}) )) )).value, [1 1]), [2 1]));  % bound once
  promo_k2 = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, promo_ictab("V_57_lumped"));  % bound once
  if nargin == 0
    result.derivative = @promo_derivative;
    result.initial = @initial;
    return;
  end
  [result, outs] = promo_derivative(varargin{:});
function [dy, outs] = promo_derivative(t, y, par)
  dy = zeros(1, 1);
  V_57_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, y(1:1));
  % V_39 — bound once in the dispatcher
  % V_54 — bound once in the dispatcher
  % V_57_convection_transport — bound once in the dispatcher
  % V_34_environment — bound once in the dispatcher
  % V_34_lumped — bound once in the dispatcher
  function r = promo_balance(u)
    V_56_convection_transport = MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, u(1:2));
    dV_57_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, u(3:3));
    V_56_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, V_56_convection_transport.value([2]));  % port gather
    promo_r0 = (promo_k1) - V_56_convection_transport;
    promo_r1 = (MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, reshape((reducesum(( einsum(F_conv_lumped, V_56_lumped) ), {'A_conv'})).value, [1 1]))) - dV_57_lumped;
    promo_r2 = (MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, repmat(reshape((reducesum(( einsum(F_conv_convection_transport, V_56_convection_transport) ), {'A_conv'})).value, [1 1]), [2 1]))) - V_57_convection_transport;
    r = [promo_r0.value(:); promo_r1.value(:); promo_r2.value(:)];
  end
  promo_u = promo_solve_once(@promo_balance, 3);
  V_56_convection_transport = MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, promo_u(1:2));
  dV_57_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, promo_u(3:3));
  dy(1:1) = dV_57_lumped.value(:);
  outs.V_56_convection_transport = V_56_convection_transport.value;  % §21 output
end

function y0 = initial(par, steady_state)
  % V_39 — bound once in the dispatcher
  % V_54 — bound once in the dispatcher
  % V_57_convection_transport — bound once in the dispatcher
  % V_34_environment — bound once in the dispatcher
  % V_34_lumped — bound once in the dispatcher
  function r = promo_t0(u)  %% t=0 residual system
    V_57_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, u(1:1));
    V_56_convection_transport = MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, u(2:3));
    dV_57_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, u(4:4));
    if steady_state
      totalDiff = @(x, y) x .* 0;  %% der = 0
    end
    V_56_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, V_56_convection_transport.value([2]));  % port gather
    promo_r0 = (promo_k1) - V_56_convection_transport;
    promo_r1 = (MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, reshape((reducesum(( einsum(F_conv_lumped, V_56_lumped) ), {'A_conv'})).value, [1 1]))) - dV_57_lumped;
    promo_r2 = (MultiDimVar({'A_conv', 'N'}, [2 1], {'A_conv', 'N'}, repmat(reshape((reducesum(( einsum(F_conv_convection_transport, V_56_convection_transport) ), {'A_conv'})).value, [1 1]), [2 1]))) - V_57_convection_transport;
    r = [promo_r0.value; promo_r1.value; promo_r2.value];
    if steady_state
      r = [r; dV_57_lumped.value];  % der = 0
    else
      promo_e0 = (promo_k2) - V_57_lumped;  % IC pin
      r = [r; promo_e0.value];
    end
  end
  promo_u = promo_solve_balance(@promo_t0, 4);
  V_57_lumped = MultiDimVar({'A_conv', 'N'}, [1 1], {'A_conv', 'N'}, promo_u(1:1));
  y0 = [V_57_lumped.value(:)];
end


% the shared data file — the language-neutral half
% of the data/code split (parsed once, persistent)
function d = promo_model_data()
  persistent d_
  if isempty(d_)
    d_ = jsondecode(fileread(fullfile(fileparts(mfilename('fullpath')), 'model_data.json')));
  end
  d = d_;
end

function a = promo_mx(n)
  d = promo_model_data();
  e = d.matrices.(n);
  a = sparse(e.i + 1, e.j + 1, e.v, e.m, e.n);
end

function a = promo_shape(e)
  % jsondecode hands column vectors — row them,
  % fliplr on a column is a no-op
  d = e.dims(:).';
  if numel(d) <= 1, a = e.flat(:); return; end
  a = permute(reshape(e.flat, fliplr(d)), fliplr(1:numel(d)));
end

function a = promo_tab(n)
  d = promo_model_data();
  a = promo_shape(d.values.(n));
end

function a = promo_ictab(n)
  d = promo_model_data();
  a = promo_shape(d.ics.(n));
end

function u = promo_solve_balance(fun, count)
  if count == 0
    u = zeros(0, 1); r = fun(u);
    if any(~isfinite(r)) || any(abs(r) > 1e-8), error('inconsistent prescribed balance'); end
    return;
  end
  % Emitted balance residuals are affine in u — solve
  % A u = -r(0) with a finite-difference A, cached per
  % residual (keyed on the function name) so the inner
  % solve in promo_derivative costs ~2 residual evals
  % per ODE step instead of an fsolve.  fsolve stays
  % the fallback for genuinely nonlinear residuals.
  persistent affine nonlin;
  if isempty(affine), affine = struct(); nonlin = struct(); end
  key = ['f_' regexprep(func2str(fun), '[^A-Za-z0-9_]', '_')];
  if isfield(nonlin, key)
    u = promo_fsolve_balance(fun, count); return;
  end
  r0 = fun(zeros(count, 1));
  if isfield(affine, key)
    u = -(affine.(key) \ r0);
    r = fun(u);
    if all(isfinite(r)) && all(abs(r) <= 1e-8), return; end
    affine = rmfield(affine, key); nonlin.(key) = true;
    u = promo_fsolve_balance(fun, count); return;
  end
  A = zeros(numel(r0), count);
  for k = 1:count
    ek = zeros(count, 1); ek(k) = 1;
    A(:,k) = fun(ek) - r0;
  end
  if rank(A) >= count
    u = -(A \ r0);
    r = fun(u);
    if all(isfinite(r)) && all(abs(r) <= 1e-8)
      affine.(key) = A; return;
    end
  end
  nonlin.(key) = true;
  u = promo_fsolve_balance(fun, count);
end

function u = promo_solve_once(fun, count)
  % The emitter proved this residual time-invariant:
  % every input is a dispatcher constant or a solve
  % unknown, so the solution never changes — solve
  % once, then reuse it for the rest of the run.
  persistent cache;
  if isempty(cache), cache = struct(); end
  key = ['f_' regexprep(func2str(fun), '[^A-Za-z0-9_]', '_')];
  if isfield(cache, key), u = cache.(key); return; end
  u = promo_solve_balance(fun, count);
  cache.(key) = u;
end

function u = promo_fsolve_balance(fun, count)
  options = optimset('TolFun', 1e-12, 'TolX', 1e-12, 'Display', 'off');
  [u, r, flag, output, jac] = fsolve(fun, zeros(count, 1), options);
  if flag <= 0 || any(~isfinite(r)) || any(abs(r) > 1e-8), error('prescribed balance solve failed'); end
  if rank(jac) < count, error('prescribed balance system is underdetermined'); end
end
end