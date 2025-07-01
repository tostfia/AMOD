import numpy as np
from analysis.solver import *
from config import *
import pandas as pd
import logging
import cplex
import datetime
import os

from utility.facilityLocation import FacilityLocationModel
from utility.utils import getStatistics, modulus

logging.basicConfig(filename='resolution.log', format='%(asctime)s - %(message)s', level=logging.INFO,
                    datefmt='%d-%b-%y %H:%M:%S')
columns = ["name", "nvar", "nconstraints", "optimal_sol", "sol", "sol_is_integer", "status", "ncuts",
           "elapsed_time", "gap", "relative_gap", "iterations"]


def solveInstance(model, instance,  stats):
    logging.info("\n---------------------------------------------------")
    logging.info("Solving problem instance '" + instance + "';\n")
    stats_i = solveProblem(model, instance)
    return stats.append(pd.DataFrame(stats_i, columns=columns))


def solveProblem(model: FacilityLocationModel, instance: str):
    '''
    This function solves a specific problem instance

    Arguments:
        instance
        stats
    '''
    # Retrieve the matrixes of the problem instance
    c, A, b = getProblemData(model)
    nCols, nRows = (len(c)), (len(b))

    # Get the instance name
    name = os.path.splitext(os.path.basename(instance))[0]
    if not os.path.exists("solutions/" + name):
        os.makedirs("solutions/" + name)
    if not os.path.exists("lp/" + name):
        os.makedirs("lp/"  + name)

    path_base_log = str("solutions/"  + name)
    path_base_lp = str("lp/"  + name)

    # Program variables section ####################################################
    names, lower_bounds, upper_bounds, constraint_senses, constraint_names = initializeInstanceVariables(nCols, nRows)

    nCols = nCols + nRows

    # Populate statistics
    tot_stats = []

    # Solver section    ############################################################

    # First of all determine the optimal solution
    optimal_sol = determineOptimal(model,instance)

    with cplex.Cplex() as mkp, open("cplexEvents.log", "w") as f:

        # set MKP
        mkp.set_problem_name(name)
        mkp.objective.set_sense(mkp.objective.sense.maximize)
        mkp.set_log_stream(f)
        mkp.set_error_stream(f)
        mkp.set_warning_stream(f)
        mkp.set_results_stream(f)
        params = mkp.parameters
        # Disable presolve
        params.preprocessing.presolve.set(0)
        params.preprocessing.linear.set(0)
        params.preprocessing.reduce.set(0)

        # Add variables & Slack --------------------------------------------------------------------
        mkp.variables.add(names=names)
        # Add variables
        for i in range(nCols - nRows):
            mkp.variables.set_lower_bounds(i, lower_bounds[i])
            mkp.variables.set_upper_bounds(i, upper_bounds[i])
        # Add slack
        for i in range(nCols - nRows, nCols):
            mkp.variables.set_lower_bounds(i, lower_bounds[i])
        # Add slack to constraints
        A = A.tolist()
        for row in range(nRows):
            for slack in range(nRows):
                if row == slack:
                    A[row].append(1)
                else:
                    A[row].append(0)

        # Add contraints to Cplex ------------------------------------------------------------------
        for i in range(nRows):
            mkp.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=[j for j in range(nCols)], val=A[i])], rhs=[b[i]],
                                       names=[constraint_names[i]], senses=[constraint_senses[i]])
        # Add objective function -----------------------------------------------------------
        for i in range(nCols - nRows):
            mkp.objective.set_linear([(i, c[i])])

        # Total time
        total_time = 0.0
        ###########################################
        # Start time for first iteration
        start_iteration_time = datetime.datetime.now()
        # Resolve the problem instance with 0 cuts
        mkp.solve()
        # Report the results with 0 cut
        logging.info("\n\t\t\t\t\t\t*** RELAXED PL SOLUTION (UPPER BOUND) ***")
        sol, sol_type, status = print_solution(mkp)
        if not os.path.exists(path_base_log + "/iteration0"):
            os.makedirs(path_base_log + "/iteration0")
        if not os.path.exists(path_base_lp + "/iteration0"):
            os.makedirs(path_base_lp + "/iteration0")
        mkp.write(path_base_lp + "/iteration0/0_cut.lp")
        mkp.solution.write(path_base_log + "/iteration0/0_cut.log")
        elapsed_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
        logging.info("Iteration time: %s Milliseconds", elapsed_time)
        # Append to statistics with 0 cuts
        tot_stats.append(
            getStatistics(name, nCols - nRows, nRows, optimal_sol, sol, sol_type, status, 0, elapsed_time,
                          0))

        # Generate gormory cuts
        n_cuts, b_bar = get_tableau(mkp)
        gc_lhs, gc_rhs = initialize_fract_gc(n_cuts, nCols, mkp, names, b_bar)
        cuts, cut_limits, cut_senses = generate_gc(mkp, A, gc_lhs, gc_rhs, names)

        # Add the cuts sequentially and solve the problem (without slack variables)
        break_before = 0

        # Start time for first iteration
        start_iteration_time = datetime.datetime.now()
        for i in range(len(cuts)):
            mkp.linear_constraints.add(
                lin_expr=[cplex.SparsePair(ind=[j for j in range(nCols - nRows)], val=cuts[i])],
                senses=[cut_senses[i]],
                rhs=[cut_limits[i]],
                names=["cut_" + str(i + 1)])
            mkp.set_problem_name(name + "_cut_n" + str(i + 1))
            logging.info(
                "\n\t\t\t\t\t Resolution of the problem called '" + name + "': " + str(i + 1) + " Gomory cuts applied.")
            mkp.solve()
            elapsed_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
            sol, sol_type, status = print_solution(mkp)
            if status == 'infeasible':
                break_before = 1
                break
            tot_stats.append(
                getStatistics(name, nCols - nRows, (nRows + len(cuts)), optimal_sol, sol, sol_type,
                              status, i + 1, elapsed_time, 1))
            if not os.path.exists(path_base_lp + "/iteration1"):
                os.makedirs(path_base_lp + "/iteration1")
            if not os.path.exists(path_base_log + "/iteration1"):
                os.makedirs(path_base_log + "/iteration1")
            mkp.write(path_base_lp + "/iteration1/" + str(i + 1) + "_cut.lp")
            mkp.solution.write(path_base_log + "/iteration1/" + str(i + 1) + "_cut.log")

        iteration_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
        total_time += iteration_time
        logging.info("Iteration time: %s Milliseconds", iteration_time)
        mkp.end()


    if break_before == 1:
        return tot_stats

    iteration = 1
    rel_gap = 9999999999999999.0
    sol_type = "optimal"
    c = 0
    while (total_time <= TIME_LIMIT and rel_gap > THRESHOLD_GAP and status == "optimal"):
        start_iteration_time = datetime.datetime.now()
        iteration += 1
        old_sol = sol
        sol, sol_type, status, cuts, cut_limits, tot_stats = iterateGomory(name, model, cuts,
                                                                           cut_limits, tot_stats, optimal_sol,
                                                                           iteration)
        if sol == old_sol:
            c += 1;
        if (optimal_sol == 0):
            rel_gap = 1
        else:
            rel_gap = modulus(sol, optimal_sol) / (optimal_sol + pow(10, -10))
        # Get new time
        iteration_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
        total_time = total_time + iteration_time
        logging.info("Iteration time: %s Milliseconds", iteration_time)

    logging.info("Total time: %s Milliseconds", total_time)
    return tot_stats


def iterateGomory(name,  model:FacilityLocationModel, cuts, cut_limits, tot_stats, optimal_sol, iteration):
    '''
    This function solves a  gomory iteration's algorithm
    '''

    c, A, b = getProblemData(model)
    newA = A.tolist()
    newB = b.tolist()
    for i in range(len(cuts)):
        newA.append(cuts[i])
        newB.append(cut_limits[i])

    A = np.asarray(newA, dtype=np.float64)
    b = np.asarray(newB, dtype=np.float64)

    nCols, nRows = (len(c)), (len(b))

    # Get the instance name
    path_base_log = str("solutions/"  + name)
    path_base_lp = str("lp/" + name)

    if not os.path.exists(path_base_log + "/iteration" + str(iteration)):
        os.makedirs(path_base_log + "/iteration" + str(iteration))
    if not os.path.exists(path_base_lp + "/iteration" + str(iteration)):
        os.makedirs(path_base_lp + "/iteration" + str(iteration))

    # Program variables section ####################################################
    names, lower_bounds, upper_bounds, constraint_senses, constraint_names = initializeInstanceVariables(nCols, nRows)
    nCols = nCols + nRows

    # Populate statistics
    n_cuts = len(cuts)
    with cplex.Cplex() as mkp, open("cplexEvents.log", "w") as f:
        # set mkp
        mkp.set_problem_name(name)
        mkp.objective.set_sense(mkp.objective.sense.maximize)
        mkp.set_log_stream(f)
        mkp.set_error_stream(f)
        mkp.set_warning_stream(f)
        mkp.set_results_stream(f)
        params = mkp.parameters
        # Disable presolve
        params.preprocessing.presolve.set(0)
        params.preprocessing.linear.set(0)
        params.preprocessing.reduce.set(0)

        # Add variables & Slack --------------------------------------------------------------------
        mkp.variables.add(names=names)
        # Add variables
        for i in range(nCols - nRows):
            mkp.variables.set_lower_bounds(i, lower_bounds[i])
            mkp.variables.set_upper_bounds(i, upper_bounds[i])
        # Add slack
        for i in range(nCols - nRows, nCols):
            mkp.variables.set_lower_bounds(i, lower_bounds[i])
        # Add slack to constraints
        A = A.tolist()
        for row in range(nRows):
            for slack in range(nRows):
                if row == slack:
                    A[row].append(1)
                else:
                    A[row].append(0)

        # Add contraints to Cplex ------------------------------------------------------------------
        for i in range(nRows):
            mkp.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=[j for j in range(nCols)], val=A[i])], rhs=[b[i]],
                                       names=[constraint_names[i]], senses=[constraint_senses[i]])
        # Add objective function -----------------------------------------------------------
        for i in range(nCols - nRows):
            mkp.objective.set_linear([(i, c[i])])
        # solve mkp with 0 cuts
        mkp.solve()
        # get solution with 0 cuts
        sol, sol_type, status = print_solution(mkp)
        mkp.write(path_base_lp + "/iteration" + str(iteration) + "/0_cut.lp")
        mkp.solution.write(path_base_log + "/iteration" + str(iteration) + "/0_cut.log")
        ########################################################################
        n_cuts, b_bar = get_tableau(mkp)
        gc_lhs, gc_rhs = initialize_fract_gc(n_cuts, nCols, mkp, names, b_bar)
        new_cuts, new_cut_limits, new_cut_senses = generate_gc(mkp, A, gc_lhs, gc_rhs, names)
        # start ime
        start_iteration_time = datetime.datetime.now()
        # Add the cuts sequentially and solve the problem (without slack variables)
        for i in range(len(new_cuts)):
            mkp.linear_constraints.add(
                lin_expr=[cplex.SparsePair(ind=[j for j in range(nCols - nRows)], val=new_cuts[i])],
                senses=[new_cut_senses[i]],
                rhs=[new_cut_limits[i]],
                names=["cut_" + str(i + 1)])
            mkp.set_problem_name(name + "_cut_n" + str(i + 1))
            logging.info(
                "\n\t\t\t\t\t Resolution of the problem called '" + name + "': " + str(i + 1) + " Gomory cuts applied.")
            mkp.solve()
            sol, sol_type, status = print_solution(mkp)
            elapsed_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
            tot_stats.append(
                getStatistics(name, nCols - nRows, (nRows + len(cuts)), optimal_sol, sol, sol_type,
                              status, n_cuts + i + 1, elapsed_time, iteration))
            mkp.write(path_base_lp + "/iteration" + str(iteration) + "/" + str(i + 1) + "_cut.lp")
            mkp.solution.write(path_base_log + "/iteration" + str(iteration) + "/" + str(i + 1) + "_cut.log")

        for cut in new_cuts:
            cuts.append(cut)
        for cut_lim in new_cut_limits:
            cut_limits.append(cut_lim)

        sol, sol_type, status = print_solution(mkp)
        mkp.end()


    return sol, sol_type, status, cuts, cut_limits, tot_stats
