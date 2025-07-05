import numpy as np

from analysis.solver import Solver, initialize_instance_variables, print_solution, get_tableau, initialize_fract_gc, \
    generate_gc
from config import *
import cplex
import datetime
import os

from utility.facilityLocation import FacilityLocationModel
from utility.utils import get_statistics, modulus

class Gomory:
    def __init__(self, model:FacilityLocationModel):
        self.model=model



    def solve_problem(self, instance: str):
        print(f"=== INIZIO RISOLUZIONE PROBLEMA: {instance} ===")
        solver=Solver(self.model)
        # Retrieve the matrices of the problem instance
        c, A, b = solver.get_problem_data()
        nCols, nRows = len(c), len(b)
        print(f"Dimensioni problema: {nCols} variabili, {nRows} vincoli")
        print(f"Obiettivo: {c}")
        print(f"Matrice A shape: {A.shape}")
        print(f"Termine noto b: {b}")

    # Get the instance name
        name = os.path.splitext(os.path.basename(instance))[0]

        # Initialize problem variables
        names, lower_bounds, upper_bounds, constraint_senses, constraint_names = initialize_instance_variables(nCols, nRows)
        nCols = nCols + nRows

        # Initialize statistics collection
        tot_stats = []

        # Determine the optimal solution
        optimal_sol = solver.determine_optimal( instance)
        print(f"Soluzione ottima di riferimento: {optimal_sol}")

        print("\n--- RISOLUZIONE RILASSAMENTO INIZIALE ---")
        initial_stats = self.solve_initial_relaxation(
            name, c, A, b, nCols, nRows, names, lower_bounds, upper_bounds,
            constraint_senses, constraint_names, optimal_sol
        )

        if not initial_stats:
            print("ERRORE: Fallita risoluzione rilassamento iniziale")
            return tot_stats

        sol, sol_type, status, cuts, cut_limits, elapsed_time = initial_stats
        print(f"Rilassamento iniziale risolto: sol={sol}, status={status}, tempo={elapsed_time:.2f}ms")
        print(f"Numero di tagli generati: {len(cuts)}")
        # Add initial statistics (0 cuts)
        tot_stats.append(
            get_statistics(name, nCols - nRows, nRows, optimal_sol, sol, sol_type, status, 0, elapsed_time)
        )

        # Check if problem became infeasible after initial cuts
        if status == 'infeasible':
            print("PROBLEMA DIVENTATO INFEASIBLE DOPO TAGLI INIZIALI")
            return tot_stats

        # Main Gomory iteration loop
        print("\n--- INIZIO ITERAZIONI GOMORY ---")
        iteration = 1
        rel_gap = float('inf')
        total_time = elapsed_time
        consecutive_same_solutions = 0

        while (total_time <= TIME_LIMIT and
               rel_gap > THRESHOLD_GAP and
               status == "optimal"):
            print(f"\n### ITERAZIONE {iteration} ###")
            start_iteration_time = datetime.datetime.now()
            iteration += 1
            old_sol = sol
            print(f"Soluzione precedente: {old_sol}")
            print(f"Gap relativo corrente: {rel_gap:.6f}")
            print(f"Tempo totale trascorso: {total_time:.2f}ms")
            print(f"Soluzioni consecutive identiche: {consecutive_same_solutions}")

            # Perform Gomory iteration
            iteration_result = self.iterate_gomory(
                name, self.model, cuts, cut_limits, tot_stats, optimal_sol, iteration
            )

            if not iteration_result:
                print("ERRORE: Iterazione fallita")
                break

            sol, sol_type, status, cuts, cut_limits, iteration_stats = iteration_result
            tot_stats.extend(iteration_stats)
            print(f"Nuova soluzione: {sol}, status: {status}")
            print(f"Numero totale di tagli: {len(cuts)}")

            # Check for convergence
            if sol == old_sol:
                consecutive_same_solutions += 1
                print(f"Soluzione identica alla precedente (consecutiva #{consecutive_same_solutions})")
            else:
                consecutive_same_solutions = 0
                print("Soluzione migliorata")

            # Calculate relative gap
            if optimal_sol == 0:
                rel_gap = 1
            else:
                rel_gap = modulus(sol, optimal_sol) / (optimal_sol + 1e-10)
            print(f"Nuovo gap relativo: {rel_gap:.6f}")

            # Update total time
            iteration_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
            total_time += iteration_time

            print(f"Tempo iterazione: {iteration_time:.2f}ms")
            print(f"Tempo totale: {total_time:.2f}ms")

            # Break if we've had too many consecutive identical solutions
            if consecutive_same_solutions >= 3:
                print("STOP: Troppi consecutivi risultati identici")
                break

        print(f"\n=== FINE RISOLUZIONE ===")
        print(f"Iterazioni totali: {iteration-1}")
        print(f"Tempo totale: {total_time:.2f}ms")
        print(f"Soluzione finale: {sol}")
        print(f"Gap finale: {rel_gap:.6f}")
        print(f"Numero statistiche raccolte: {len(tot_stats)}")

        return tot_stats

    def solve_initial_relaxation(self, name, c, A, b, nCols, nRows, names, lower_bounds, upper_bounds,
                                 constraint_senses, constraint_names, optimal_sol):
        """
        Solve the initial LP relaxation and generate first set of Gomory cuts.

        Returns:
            Tuple of (sol, sol_type, status, cuts, cut_limits, elapsed_time) or None if failed
        """
        print("Inizio risoluzione rilassamento iniziale...")
        start_time = datetime.datetime.now()

        try:
            with cplex.Cplex() as mkp:
                # Configure problem
                print("Configurazione problema CPLEX...")
                mkp.set_problem_name(name)
                mkp.objective.set_sense(mkp.objective.sense.maximize)

                # Disable presolve
                params = mkp.parameters
                params.preprocessing.presolve.set(0)
                params.preprocessing.linear.set(0)
                params.preprocessing.reduce.set(0)

                # Add variables and constraints
                self.setup_cplex_problem(mkp, c, A, b, nCols, nRows, names, lower_bounds, upper_bounds,
                                         constraint_senses, constraint_names)

                # Solve initial relaxation
                mkp.solve()
                sol, sol_type, status = print_solution(mkp)
                print(f"Risultato rilassamento: sol={sol}, status={status}")

                if status == 'infeasible':
                    return None

                # Generate initial Gomory cuts
                print("Generazione tagli Gomory iniziali...")
                n_cuts, b_bar = get_tableau(mkp)
                print(f"Tableau ottenuto: {n_cuts} possibili tagli")
                gc_lhs, gc_rhs = initialize_fract_gc(n_cuts, nCols, mkp, names, b_bar)
                cuts, cut_limits, cut_senses = generate_gc(mkp, A, gc_lhs, gc_rhs, names)

                # Apply cuts and resolve
                print(f"Tagli generati: {len(cuts)}")
                for i, (cut, cut_limit, cut_sense) in enumerate(zip(cuts, cut_limits, cut_senses)):
                    print(f"Aggiungendo taglio {i+1}/{len(cuts)}")
                    mkp.linear_constraints.add(
                        lin_expr=[cplex.SparsePair(ind=list(range(nCols - nRows)), val=cut)],
                        senses=[cut_sense],
                        rhs=[cut_limit],
                        names=[f"cut_{i + 1}"]
                    )

                    mkp.solve()
                    sol, sol_type, status = print_solution(mkp)
                    print(f"Dopo taglio {i+1}: sol={sol}, status={status}")

                    if status == 'infeasible':
                        print(f"Problema diventato infeasible al taglio {i+1}")
                        break

                elapsed_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
                print(f"Rilassamento iniziale completato in {elapsed_time:.2f}ms")
                return sol, sol_type, status, cuts, cut_limits, elapsed_time

        except Exception as e:
            print(f"ERRORE nel rilassamento iniziale: {e}")
            return None


    def setup_cplex_problem(self, mkp, c, A, b, nCols, nRows, names, lower_bounds, upper_bounds,
                            constraint_senses, constraint_names):
        """
        Set up the CPLEX problem with variables, constraints, and objective.
        """
        # Add variables
        mkp.variables.add(names=names)

        # Set variable bounds
        for i in range(nCols - nRows):
            mkp.variables.set_lower_bounds(i, lower_bounds[i])
            mkp.variables.set_upper_bounds(i, upper_bounds[i])

        # Add slack variables
        for i in range(nCols - nRows, nCols):
            mkp.variables.set_lower_bounds(i, lower_bounds[i])

        # Add slack variables to constraint matrix
        A_list = A.tolist()
        for row in range(nRows):
            for slack in range(nRows):
                A_list[row].append(1 if row == slack else 0)

        # Add constraints
        for i in range(nRows):
            mkp.linear_constraints.add(
                lin_expr=[cplex.SparsePair(ind=list(range(nCols)), val=A_list[i])],
                rhs=[b[i]],
                names=[constraint_names[i]],
                senses=[constraint_senses[i]]
            )

        # Set objective function
        for i in range(nCols - nRows):
            mkp.objective.set_linear([(i, c[i])])


    def iterate_gomory(self, name, model: FacilityLocationModel, cuts, cut_limits, tot_stats, optimal_sol, iteration):
        solver= Solver(model)
        # Get problem data with current cuts
        c, A, b = solver.get_problem_data()

        # Add existing cuts to the problem
        newA = A.tolist()
        newB = b.tolist()
        for i in range(len(cuts)):
            newA.append(cuts[i])
            newB.append(cut_limits[i])

        A = np.asarray(newA, dtype=np.float64)
        b = np.asarray(newB, dtype=np.float64)
        nCols, nRows = len(c), len(b)

        # Initialize variables
        names, lower_bounds, upper_bounds, constraint_senses, constraint_names = initialize_instance_variables(nCols, nRows)
        nCols = nCols + nRows

        iteration_stats = []
        n_existing_cuts = len(cuts)

        try:
            with cplex.Cplex() as mkp:
                # Configure problem
                mkp.set_problem_name(name)
                mkp.objective.set_sense(mkp.objective.sense.maximize)

                # Disable presolve
                params = mkp.parameters
                params.preprocessing.presolve.set(0)
                params.preprocessing.linear.set(0)
                params.preprocessing.reduce.set(0)

                # Setup problem
                self.setup_cplex_problem(mkp, c, A, b, nCols, nRows, names, lower_bounds, upper_bounds,
                                         constraint_senses, constraint_names)

                # Solve current problem
                mkp.solve()
                sol, sol_type, status = print_solution(mkp)

                if status == 'infeasible':
                    return sol, sol_type, status, cuts, cut_limits, iteration_stats

                # Generate new Gomory cuts
                n_cuts, b_bar = get_tableau(mkp)
                gc_lhs, gc_rhs = initialize_fract_gc(n_cuts, nCols, mkp, names, b_bar)
                new_cuts, new_cut_limits, new_cut_senses = generate_gc(mkp, A, gc_lhs, gc_rhs, names)

                # Apply new cuts
                start_time = datetime.datetime.now()
                for i, (cut, cut_limit, cut_sense) in enumerate(zip(new_cuts, new_cut_limits, new_cut_senses)):
                    mkp.linear_constraints.add(
                        lin_expr=[cplex.SparsePair(ind=list(range(nCols - nRows)), val=cut)],
                        senses=[cut_sense],
                        rhs=[cut_limit],
                        names=[f"cut_{i + 1}"]
                    )

                    mkp.solve()
                    sol, sol_type, status = print_solution(mkp)

                    elapsed_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
                    iteration_stats.append(
                        get_statistics(name, nCols - nRows, nRows, optimal_sol, sol, sol_type,
                                       status, n_existing_cuts + i + 1, elapsed_time)
                    )

                    if status == 'infeasible':
                        print(f"Problema diventato infeasible al nuovo taglio {i+1}")
                        break

                # Update cuts lists
                cuts.extend(new_cuts)
                cut_limits.extend(new_cut_limits)
                print(f"Iterazione completata. Tagli totali: {len(cuts)}")
                return sol, sol_type, status, cuts, cut_limits, iteration_stats

        except Exception as e:
            print(f"ERRORE nell'iterazione Gomory: {e}")
            return None, "error", "error", cuts, cut_limits, iteration_stats