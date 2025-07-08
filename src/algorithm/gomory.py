import time
import datetime
import cplex


from algorithm.solver import Solver, initialize_instance_variables, print_solution, generate_gomory_fractional_cuts
from config import *
from utility.facilityLocation import FacilityLocationModel
from utility.utils import get_statistics, modulus


def calculate_gap(current_sol, optimal_sol):
    """Calcola il gap relativo tra la soluzione corrente e quella ottima."""
    if optimal_sol is None or current_sol is None:
        return float('inf')
    # Per la massimizzazione, current_sol >= optimal_sol. Il gap è (current - optimal)
    # Per la minimizzazione, current_sol <= optimal_sol. Il gap è (optimal - current)
    # Usando abs() funziona in entrambi i casi.
    gap = abs(current_sol - optimal_sol)
    denominator = abs(optimal_sol) + 1e-10
    return gap / denominator

def setup_cplex_problem(mkp, name, c, A, b, lower_bounds, upper_bounds, constraint_senses, constraint_names):
    """Imposta il problema CPLEX per il rilassamento LP."""
    nCols = len(c)
    nRows = len(b)
    all_vars_names = ["x" + str(i) for i in range(nCols)] + ["s" + str(i) for i in range(nRows)]

    mkp.set_problem_name(name)
    mkp.objective.set_sense(mkp.objective.sense.maximize)

    params = mkp.parameters
    params.preprocessing.presolve.set(0)
    params.lpmethod.set(params.lpmethod.values.primal) # Usa Simplex Primale

    mkp.variables.add(names=all_vars_names, lb=lower_bounds, ub=upper_bounds + [cplex.infinity] * nRows)

    # Aggiungi i vincoli originali con le variabili di slack
    for i in range(nRows):
        row_indices = list(range(nCols)) + [nCols + i] # Aggiunge l'indice della slack var
        row_values = A[i].tolist() + [1.0] # Aggiunge il coefficiente della slack var
        mkp.linear_constraints.add(
            lin_expr=[cplex.SparsePair(ind=row_indices, val=row_values)],
            rhs=[b[i]],
            names=[constraint_names[i]],
            senses=['E'] # Ora i vincoli sono di uguaglianza grazie alle slack
        )

    mkp.objective.set_linear(list(enumerate(c)))


def _print_analysis_results(instance_name: str, results: dict):
    """Metodo helper privato per stampare la tabella dei risultati."""
    print("\n" + "="*95)
    print(f"RISULTATI COMPARATIVI PER: {instance_name}")
    print("="*95)
    header = (f"{'Modalità':<20} | {'Stato':<22} | {'Obiettivo':>15} | "
              f"{'Gap (%)':>10} | {'Nodi':>8} | {'Tagli Gomory':>12} | {'Tempo (s)':>10}")
    print(header)
    print("-"*95)

    for mode_name, res in sorted(results.items()):
        obj_str = f"{res['objective']:.2f}" if isinstance(res['objective'], float) else res['objective']
        gap_str = f"{res['gap']:.4f}" if isinstance(res['gap'], float) else res['gap']

        row = (f"{mode_name:<20} | {res['status']:<22} | {obj_str:>15} | "
               f"{gap_str:>10} | {res['nodes']:>8} | {res['gomory_cuts']:>12} | {res['time_sec']:>10.2f}")
        print(row)
    print("="*95)


class Gomory:
    def __init__(self, model: FacilityLocationModel):
        self.model = model
        self.solver = Solver(self.model)

    def solve_problem(self, instance_path_str: str):
        instance_path = Path(instance_path_str)
        print(f"\n=== INIZIO RISOLUZIONE (GOMORY SU MAXIMIZE): {instance_path.name} ===")

        # 1. Ottieni i dati del problema come MASSIMIZZAZIONE
        c, A, b = self.solver.get_problem_data(maximize=True)
        nCols, nRows = len(c), len(b)

        name = instance_path.stem
        tot_stats = []

        # 2. Ottieni la soluzione ottima di riferimento (sempre in modalità massimizzazione)
        optimal_sol = self.solver.determine_optimal(instance_path, maximize=True)
        if optimal_sol is None:
            return []

        names, lower_bounds, upper_bounds, constraint_senses, constraint_names = initialize_instance_variables(nCols, nRows)

        try:
            with cplex.Cplex() as mkp:
                # 3. Setup del problema LP iniziale (massimizzazione)
                # Dobbiamo creare un modello con slack esplicite per accedere al tableau

                mkp.set_problem_type(mkp.problem_type.LP)
                mkp.set_problem_name(name+"_LP_Relaxation")
                mkp.objective.set_sense(mkp.objective.sense.maximize)

                params = mkp.parameters
                params.mip.cuts.set(-1) # Disattiva tutti
                params.mip.cuts.gomory.set(2) # Attiva i tagli di Gomory in modo aggressivo

                params.preprocessing.presolve.set(0)
                params.lpmethod.set(params.lpmethod.values.primal)#usa simplex

                var_names = ["x" + str(i) for i in range(nCols)]

                mkp.variables.add(
                    obj=c,
                    lb=[0.0] * nCols,
                    ub=[1.0] * nCols, # Bound per le variabili binarie originali
                    names=var_names
                )
                mkp.linear_constraints.add(
                    lin_expr=[cplex.SparsePair(ind=list(range(nCols)), val=A[i]) for i in range(nRows)],
                    rhs=b.tolist(),
                    senses=['L'] * nRows,
                    names=["c"+str(i) for i in range(nRows)]# Vincoli di uguaglianza
                )

                # 4. Risolvi il rilassamento iniziale
                print("\n--- RISOLUZIONE RILASSAMENTO INIZIALE ---")
                start_time = datetime.datetime.now()
                mkp.solve()
                sol, sol_type, status = print_solution(mkp)
                elapsed_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
                if status == 'integer optimal solution':
                    print("!!DEBUF FALLITO : CPLEX sta ancora risolvendo un MIP")
                # Aggiungi statistiche iniziali
                stats_iter_0 = get_statistics(name, nCols, nRows, optimal_sol, sol, sol_type, status, 0, elapsed_time, 0)
                tot_stats.append(stats_iter_0)

                if status != 'optimal':
                    print("ERRORE: Rilassamento iniziale non risolto ottimamente.")
                    return tot_stats

                # 5. Ciclo di Gomory
                iteration = 1
                total_time = elapsed_time
                num_total_cuts = 0

                while (total_time <= TIME_LIMIT and
                       modulus(sol,optimal_sol)/(abs(optimal_sol)+1e-10) > THRESHOLD_GAP and
                       status == "optimal" and iteration <= MAX_ITERATIONS):

                    print(f"\n### ITERAZIONE GOMORY {iteration} ###")
                    start_iteration_time = datetime.datetime.now()

                    # Genera nuovi tagli
                    new_cuts_data= generate_gomory_fractional_cuts(mkp, nCols)

                    if not new_cuts_data:
                        print("STOP: Nessun nuovo taglio frazionario generato. La soluzione potrebbe essere ottima intera.")
                        break

                    print(f"Generati {len(new_cuts_data)} nuovi tagli.")
                    num_total_cuts += len(new_cuts_data)
                    for i, cut_info in enumerate(new_cuts_data):
                        mkp.linear_constraints.add(
                            lin_expr=[cplex.SparsePair(ind=cut_info['indices'], val=cut_info['coeffs'])],
                            senses=[cut_info['sense']],
                            rhs=[cut_info['rhs']],
                            names=[f"gfc_{iteration}_{i}"]
                        )


                    # Risolvi il modello aggiornato
                    mkp.solve()
                    sol, sol_type, status = print_solution(mkp)

                    # Raccogli statistiche
                    iteration_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
                    total_time += iteration_time
                    current_stats = get_statistics(name, nCols, nRows + num_total_cuts, optimal_sol, sol, sol_type, status, num_total_cuts, total_time, iteration)
                    tot_stats.append(current_stats)
                    print(f"Nuova soluzione: {sol:.4f}, status: {status}, gap: {current_stats.get('relative_gap', float('inf')):.4f}")

                    if status != 'optimal':
                        print(f"STOP: Il problema è diventato {status}.")
                        break

                    iteration += 1

                print(f"\n=== FINE RISOLUZIONE ===")
                print(f"Iterazioni totali: {iteration - 1}, Tagli totali: {num_total_cuts}")
                # Stampa il risultato finale riconvertito in MINIMIZZAZIONE
                if sol is not None:
                    print(f"Valore finale (MAX): {sol:.4f} -> Valore finale (MIN): {-sol:.4f}")

                return tot_stats

        except cplex.CplexError as e:
            print(f"ERRORE CPLEX in solve_problem: {e}")
            return tot_stats
        except Exception as e:
            print(f"ERRORE IMPREVISTO in solve_problem: {e}")
            raise # Rilancia l'eccezione per un debug più facile
            return tot_stats

    def analyze_with_cplex_cuts(self, instance_path: Path):
        """
        Analizza un'istanza usando i tagli integrati di CPLEX per valutare
        l'impatto dei tagli di Gomory in un ambiente professionale.
        """
        print(f"\n\U0001F52D ANALISI AVANZATA (CPLEX CUTS) ISTANZA: {instance_path.name} \U0001F52D")

        # Ottieni i dati del problema per la minimizzazione
        c, A, b = self.solver.get_problem_data()
        nCols = len(c)

        results = {}

        # Definisci le modalità di test
        modes = {
            "1. CPLEX Default": {"cuttype": 0},
            "2. No Cuts": {"cuttype": -1},
            "3. Gomory Only": {"cuttype": -1, "gomory": 2}
        }

        for mode_name, settings in sorted(modes.items()):
            print(f"\n--- Esecuzione in modalità: {mode_name} ---")

            with cplex.Cplex() as mkp:
                mkp.set_problem_name(f"{instance_path.stem}_{mode_name.replace(' ', '_')}")
                mkp.objective.set_sense(mkp.objective.sense.minimize)

                mkp.set_log_stream(None)
                mkp.set_results_stream(None)

                params = mkp.parameters
                params.timelimit.set(300) # Limite di tempo di 5 minuti

                # Imposta i parametri per i tagli
                if "cuttype" in settings:
                    params.mip.strategy.cuttype.set(settings["cuttype"])

                if "gomory" in settings:
                    params.mip.cuts.gomory.set(settings["gomory"])

                # Setup del modello ILP
                mkp.variables.add(obj=c, lb=[0.0] * nCols, ub=[1.0] * nCols, types=[mkp.variables.type.binary] * nCols)
                mkp.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=list(range(nCols)), val=A[i]) for i in range(len(b))],
                                           rhs=b.tolist(), senses=['L'] * len(b))

                start_time = time.time()
                mkp.solve()
                end_time = time.time()

                # Raccogli le statistiche
                solution = mkp.solution
                stats = {
                    "status": solution.get_status_string(),
                    "objective": 'N/A',
                    "gap": 'N/A',
                    "nodes": solution.progress.get_num_nodes_processed(),
                    "time_sec": end_time - start_time,
                    "gomory_cuts": 0
                }

                if solution.get_status() in [101, 102, 107]: # optimal, integer optimal, time limit
                    stats["objective"] = solution.get_objective_value()
                    stats["gap"] = solution.MIP.get_mip_relative_gap() * 100
                    stats["gomory_cuts"] = solution.MIP.get_num_cuts(solution.MIP.cut_type.gomory)

                results[mode_name] = stats

        # Stampa la tabella di confronto finale
        _print_analysis_results(instance_path.name, results)

        return results # Restituisce i risultati per un'eventuale aggregazione

