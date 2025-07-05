import os
from typing import Tuple
import numpy as np
import fractions
import logging
import cplex
import io

from utility.facilityLocation import FacilityLocationModel


def initialize_fract_gc(n_cuts, ncol, prob, varnames, b_bar):

    cuts = np.zeros([n_cuts, ncol])
    cut_limits = []
    gc_sense = [''] * n_cuts
    gc_rhs = np.zeros(n_cuts)
    gc_lhs = np.zeros([n_cuts, ncol])
    rmatbeg = np.zeros(n_cuts)
    rmatind = np.zeros(ncol)
    rmatval = np.zeros(ncol)
    logging.info('Generating Gomory cuts...\n')
    cut = 0  # Index of cut to be added
    for i in range(n_cuts):
        idx = 0
        output = io.StringIO()
        if np.floor(b_bar[i]) != b_bar[i]:
            print(f'Row {i + 1} gives cut -> ', end='', file=output)
            z = np.copy(prob.solution.advanced.binvarow(i))  # Use np.copy to avoid changing the
            # optimal tableau in the problem instance
            rmatbeg[cut] = idx
            for j in range(ncol):
                z[j] = z[j] - np.floor(z[j])

                if z[j] != 0:
                    rmatind[idx] = j
                    rmatval[idx] = z[j]
                    idx += 1
                # Print the cut
                if z[j] > 0:
                    print('+', end='', file=output)
                if (z[j] != 0):
                    fj = fractions.Fraction(z[j])
                    fj = fj.limit_denominator()
                    num, den = (fj.numerator, fj.denominator)
                    print(f'{num}/{den} {varnames[j]} ', end='', file=output)

            gc_lhs[i, :] = z
            cuts[i, :] = z
            gc_rhs[cut] = b_bar[i] - np.copy(np.floor(b_bar[i]))  # np.copy as above
            gc_sense[cut] = 'L'
            gc_rhs_i = fractions.Fraction(gc_rhs[cut]).limit_denominator()
            num = gc_rhs_i.numerator
            den = gc_rhs_i.denominator
            print(f'>= {num}/{den}', file=output)
            cut_limits.append(gc_rhs[cut])
            cut += 1
            contents = output.getvalue()
            output.close()
            logging.info(contents)
    return gc_lhs, gc_rhs


def print_solution(prob: cplex.Cplex()):
    '''
    This function print solution of problem (cplex.Cplex())

    Arguments:
        problem -- cplex.Cplex()

    '''
    ncol = len(prob.variables.get_cols())
    nrow = len(prob.linear_constraints.get_rows())
    varnames = prob.variables.get_names()
    slack = np.round(prob.solution.get_linear_slacks(), 3)
    x = np.round(prob.solution.get_values(), 3)

    # Log everything about the solutions found
    print("Solution status = %s", prob.solution.status[prob.solution.get_status()])
    print(" Solution value  = %f\n", prob.solution.get_objective_value())
    print("SLACKS SITUATION:")
    for i in range(nrow):
        print(f'-> Row {i}:  Slack = {slack[i]}')
    print("\n\t\t\t\t\t PROBLEM VARIABLES:")
    for j in range(ncol):
        print(f'-> Column {j} (variable {varnames[j]}):  Value = {x[j]}')

    sol = prob.solution.get_objective_value()
    sol_type = abs(sol-round(sol))<1e-6
    status = prob.solution.status[prob.solution.get_status()]
    return sol, sol_type, status


def get_lhs_rhs(prob, cut_row, cut_rhs, A):
    ncol = len(A[0])
    cut_row = np.append(cut_row, cut_rhs)
    b = np.array(prob.linear_constraints.get_rhs())
    A = np.append(A, b.reshape(-1, 1), axis=1)
    plotted_vars = np.nonzero(prob.objective.get_linear())[0]
    # Assumption: plotted variables are at the beginning of the initial tableau
    for i, sk in enumerate(range(len(plotted_vars), ncol)):
        cut_coef = cut_row[sk]
        cut_row -= A[i, :] * cut_coef
    lhs = cut_row[:len(plotted_vars)]
    rhs = cut_row[ncol:]
    return lhs, rhs


def generate_gc(mkp, A, gc_lhs, gc_rhs, names):
    '''

    Arguments:
        mkp
        A
        gc_lhs
        gc_rhs
        names
    returns:
        cuts
        cuts_limits
        cut_senses
    '''
    logging.info('*** GOMORY CUTS ***\n')
    cuts = []
    cuts_limits = []
    cut_senses = []
    for i, gc in enumerate(gc_lhs):
        output = io.StringIO()
        cuts.append([])
        lhs, rhs = get_lhs_rhs(mkp, gc_lhs[i], gc_rhs[i], A)
        # Print the cut
        for j in range(len(lhs)):
            if -lhs[j] > 0:
                print('+', end='', file=output)
            if -lhs[j] != 0:
                print(f'{-lhs[j]} {names[j]} ', end='', file=output)
                cuts[i].append(-lhs[j])
            if -lhs[j] == 0:
                print(f'{-lhs[j]} {names[j]} ', end='', file=output)
                cuts[i].append(0)
        print(f'<= {-rhs[0]}\n', end='', file=output)
        cuts_limits.append(-rhs[0])
        cut_senses.append('L')
        contents = output.getvalue()
        output.close()
        logging.info(contents)
    return cuts, cuts_limits, cut_senses


def initialize_instance_variables(nCols, nRows):
    names = []
    lower_bounds = []
    upper_bounds = []
    constraint_names = []
    constraint_senses = []

    # Variables
    for i in range(nCols):
        names.append("x" + str(i))
        lower_bounds.append(0.0)
        upper_bounds.append(1.0)
    # Constraint
    for i in range(nRows):
        constraint_names.append("c" + str(i))
        constraint_senses.append("L")
    # Slack
    for i in range(nRows):
        names.append("s" + str(i))
        lower_bounds.append(0.0)
    return names, lower_bounds, upper_bounds, constraint_senses, constraint_names


def get_tableau(prob):

    binv_a = np.array(prob.solution.advanced.binvarow())

    nrow = binv_a.shape[0]
    ncol = binv_a.shape[1]
    b_bar = np.zeros(nrow)
    varnames = prob.variables.get_names()
    b = prob.linear_constraints.get_rhs()
    binv = np.array(prob.solution.advanced.binvrow())
    b_bar = np.matmul(binv, b)
    idx = 0  # Compute the nonzeros
    n_cuts = 0  # Number of fractional variables (cuts to be generated)
    logging.info('\n\t\t\t\t\t LP relaxation final tableau:\n')
    for i in range(nrow):
        output_t = io.StringIO()
        z = prob.solution.advanced.binvarow(i)
        for j in range(ncol):
            if z[j] > 0:
                print('+', end='', file=output_t)
            zj = fractions.Fraction(z[j]).limit_denominator()
            num = zj.numerator
            den = zj.denominator
            if num != 0 and num != den:
                print(f'{num}/{den} {varnames[j]} ', end='', file=output_t)
            elif num == den:
                print(f'{varnames[j]} ', end='', file=output_t)
            if np.floor(z[j] + 0.5) != 0:
                idx += 1
        b_bar_i = fractions.Fraction(b_bar[i]).limit_denominator()
        num = b_bar_i.numerator
        den = b_bar_i.denominator
        print(f'= {num}/{den}', file=output_t)
        contents = output_t.getvalue()
        logging.info("%s", contents)
        output_t.close()
        # Count the number of cuts to be generated
        if np.floor(b_bar[i]) != b_bar[i]:
            n_cuts += 1
    logging.info("Cuts to generate: %d", n_cuts)
    return n_cuts, b_bar


class Solver:
    def __init__(self, model: FacilityLocationModel):
        self.model = model

    def get_problem_data(self):
        p = self.model.get_num_facilities()
        r = self.model.get_num_customers()

        fixed_costs = self.model.get_fixed_costs()
        assignment_costs = self.model.get_assignment_costs()

        # Controllo dimensioni
        assert len(fixed_costs) == p, f"Mismatch fixed_costs length: expected {p}, got {len(fixed_costs)}"
        assert len(assignment_costs) == r, f"Mismatch assignment_costs rows: expected {r}, got {len(assignment_costs)}"
        for idx, row in enumerate(assignment_costs):
            assert len(row) == p, f"Mismatch assignment_costs cols at row {idx}: expected {p}, got {len(row)}"

        n_vars = p + (r * p)

        # Conversione sicura dei costi fissi
        try:
            fixed_costs_float = [float(cost) for cost in fixed_costs]
        except (ValueError, TypeError) as e:
            print(f"Errore nella conversione fixed_costs: {e}")
            print(f"fixed_costs: {fixed_costs}")
            raise ValueError(f"fixed_costs contiene valori non numerici: {e}")

        # Conversione sicura dei costi di assegnazione
        try:
            assignment_costs_float = []
            for i, row in enumerate(assignment_costs):
                assignment_costs_float.append([float(cost) for cost in row])
        except (ValueError, TypeError) as e:
            print(f"Errore nella conversione assignment_costs[{i}]: {e}")
            print(f"Riga problematica: {row}")
            raise ValueError(f"assignment_costs contiene valori non numerici: {e}")

        # Creazione del vettore c
        c = np.zeros(n_vars, dtype=np.float64)
        c[:p] = fixed_costs_float

        for u in range(p):
            for v in range(r):
                c[p + u * r + v] = assignment_costs_float[v][u]

        # ... resto della funzione rimane uguale
        A_list = []
        b_list = []

        # Vincoli domanda (sum_u y[u,v] = 1) in due disuguaglianze
        for v in range(r):
            row = np.zeros(n_vars, dtype=np.float64)
            for u in range(p):
                row[p + u * r + v] = 1.0
            A_list.append(row)
            b_list.append(1.0)

            A_list.append(-row)
            b_list.append(-1.0)

        # Vincoli coerenza: y[u,v] - x[u] <= 0
        for u in range(p):
            for v in range(r):
                row = np.zeros(n_vars, dtype=np.float64)
                row[p + u * r + v] = 1.0
                row[u] = -1.0
                A_list.append(row)
                b_list.append(0.0)

        A = np.vstack(A_list)
        b = np.array(b_list, dtype=np.float64)

        return c, A, b

    def determine_optimal(self, instance):

        c, A, b = self.get_problem_data()
        nCols, nRows = (len(c), len(b))
        # Get the instance name
        name = os.path.splitext(os.path.basename(instance))[0]
        cplexlog = name + ".log"
        # Program variables section ####################################################
        names = []
        all_constraints = []
        constraint_names = []
        constraint_senses = []
        # Variables
        for i in range(nCols):
            names.append("x" + str(i))
        # Constraint
        for i in range(nRows):
            constraint_names.append("c" + str(i))
            constraint_senses.append("L")
        with cplex.Cplex() as mkp:
            mkp.set_problem_name(name)
            mkp.objective.set_sense(mkp.objective.sense.maximize)
            mkp.set_log_stream(None)
            mkp.set_error_stream(None)
            mkp.set_warning_stream(None)
            mkp.set_results_stream(None)
            params = mkp.parameters
            # Disable presolve
            params.preprocessing.presolve.set(0)
            # Add variables & Slack --------------------------------------------------------------------
            mkp.variables.add(names=names, types=[mkp.variables.type.binary] * nCols)
            # Add contraints -------------------------------------------------------------------
            for i in range(nRows):
                mkp.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=[j for j in range(nCols)], val=A[i])],
                                           rhs=[b[i]], names=[constraint_names[i]], senses=[constraint_senses[i]])
                all_constraints.append(A[i])
            # Add objective function -----------------------------------------------------------
            for i in range(nCols):
                mkp.objective.set_linear([(i, c[i])])
            # Resolve the problem instance
            mkp.solve()
            # Report the results
            logging.info("\n\t\t\t\t\t\t*** OPTIMAL PLI SOLUTION ***")
            print_solution(mkp)
            mkp.write("lp/"  + name + "/optimal.lp")
            mkp.solution.write("solutions/"+ name + "/optimal.log")
            optimal_sol = mkp.solution.get_objective_value()
        return optimal_sol






