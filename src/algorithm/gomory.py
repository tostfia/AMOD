import datetime
from fractions import Fraction

import cplex
import numpy as np
from algorithm.solver import Solver, print_solution
from config import *
from utility.facilityLocation import FacilityLocationModel
from utility.utils import get_statistics, modulus


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
    """
    Classe che incapsula l'intero algoritmo dei piani di taglio di Gomory.
    Contiene la logica per il ciclo iterativo e per la generazione
    di diverse famiglie di tagli.
    """
    def __init__(self, model: FacilityLocationModel):
        self.model = model
        self.solver = Solver(self.model)
        # Questo attributo è importante per distinguere le variabili originali
        # dalle variabili di slack/ausiliarie.
        self.n_cols_original = 0


    #metodi privati per la scelta della modalità di taglio

    def _generate_gomory_fractional_cuts(self, prob: cplex.Cplex):
        """Genera Tagli Frazionari di Gomory (GFC)."""
        generated_cuts = []
        try:
            #ottiene lo stato di base delle colonne (variabili) e degli slack (righe)
            basis_col_status, _ = prob.solution.basis.get_basis()
            values = prob.solution.get_values()
            all_var_names=prob.variables.get_names()

            basic_var_indices = [i for i, s in enumerate(basis_col_status) if s == prob.solution.basis.status.basic]
            non_basic_var_indices = [i for i, s in enumerate(basis_col_status) if not (s == prob.solution.basis.status.basic)]
            tableau_rows_float = prob.solution.advanced.binvarow()
            for i,var_idx in enumerate(basic_var_indices):
                #Uso limit_denominator per evitare problemi di precisione numerica
                basic_var_value_float = values[var_idx]
                basic_var_value_frac= Fraction(basic_var_value_float).limit_denominator(1000000)
                floor_val=basic_var_value_frac.numerator//basic_var_value_frac.denominator
                fractional_part_frac= basic_var_value_frac - floor_val


                if fractional_part_frac > NUMERICAL_TOLERANCE and (1 - fractional_part_frac) > NUMERICAL_TOLERANCE:
                    tableau_row_coeffs_float=tableau_rows_float[i]
                    cut_indices, cut_coeffs = [], []
                    for non_basic_idx in non_basic_var_indices:
                        a_j_float=tableau_row_coeffs_float[non_basic_idx]
                        a_j_frac= Fraction(a_j_float).limit_denominator(1000000)
                        floor_a_j=a_j_frac.numerator//a_j_frac.denominator
                        f_j_frac=a_j_frac-floor_a_j

                        if abs(f_j_frac)>NUMERICAL_TOLERANCE:
                            cut_indices.append(all_var_names[non_basic_idx])
                            cut_coeffs.append(float(f_j_frac))
                    # Se il taglio è valido (ha almeno un coefficiente), lo aggiunge alla lista
                    if cut_indices:

                        generated_cuts.append({
                            'indices': cut_indices, 'coeffs': cut_coeffs,
                            'rhs':float(fractional_part_frac), 'sense': 'G', 'violation': float(fractional_part_frac)
                        })# 'G' Greater than or equal to
        except cplex.CplexError as e:
            print(f"ERRORE CPLEX durante la generazione dei tagli GFC: {e}")

        return generated_cuts


    def _generate_gomory_mixed_integer_cuts(self, prob: cplex.Cplex):
        """
        Genera Tagli Misti Interi di Gomory (GMI) usando l'aritmetica
        razionale per garantire la stabilità numerica.
        """
        generated_cuts = []
        try:
            basis_col_status, _ = prob.solution.basis.get_basis()
            values = prob.solution.get_values()
            all_var_names = prob.variables.get_names()

            basic_var_indices = [i for i, s in enumerate(basis_col_status) if s == prob.solution.basis.status.basic]
            non_basic_var_indices = [i for i, s in enumerate(basis_col_status) if not (s == prob.solution.basis.status.basic)]

            tableau_rows_float = prob.solution.advanced.binvarow()

            for i, var_idx in enumerate(basic_var_indices):
                var_name = all_var_names[var_idx]

                # Applica i tagli GMI solo se la variabile di base è una variabile originale ('x')
                if not var_name.startswith('x'):
                    continue

                # --- Iniziamo con i float da CPLEX ---
                basic_var_value_float = values[var_idx]

                # --- Convertiamo in Frazioni per i calcoli ---
                f_i_frac = Fraction(basic_var_value_float).limit_denominator(1000000) - np.floor(basic_var_value_float)

                # Controlla se la frazione è significativa usando la tolleranza
                if f_i_frac > NUMERICAL_TOLERANCE and (1 - f_i_frac) > NUMERICAL_TOLERANCE:
                    tableau_row_coeffs_float = tableau_rows_float[i]
                    cut_indices, cut_coeffs = [], [] # Qui memorizzeremo i float finali

                    for non_basic_idx in non_basic_var_indices:
                        a_ij_float = tableau_row_coeffs_float[non_basic_idx]
                        non_basic_var_name = all_var_names[non_basic_idx]

                        if abs(a_ij_float) < NUMERICAL_TOLERANCE:
                            continue

                        # --- Convertiamo in Frazioni per i calcoli ---
                        a_ij_frac = Fraction(a_ij_float).limit_denominator(100000)
                        coeff_frac = Fraction(0) # Inizializza il coefficiente come frazione

                        # --- Applica la formula GMI usando l'aritmetica delle frazioni ---
                        if non_basic_var_name.startswith('x'):  # Se la variabile non di base è intera
                            f_j_frac = a_ij_frac - (a_ij_frac.numerator // a_ij_frac.denominator)

                            if f_j_frac <= f_i_frac + NUMERICAL_TOLERANCE:
                                coeff_frac = f_j_frac
                            else:
                                # Controlla la divisione per zero
                                if (1 - f_i_frac) > NUMERICAL_TOLERANCE:
                                    coeff_frac = (f_i_frac / (1 - f_i_frac)) * (1 - f_j_frac)
                                else:
                                    continue # Salta questo coefficiente

                        else:  # Se la variabile non di base è continua (slack)
                            if a_ij_frac >= 0:
                                coeff_frac = a_ij_frac
                            else:
                                # Controlla la divisione per zero
                                if (1 - f_i_frac) > NUMERICAL_TOLERANCE:
                                    coeff_frac = (f_i_frac / (1 - f_i_frac)) * (-a_ij_frac)
                                else:
                                    continue # Salta questo coefficiente

                        # --- Riconverti a float solo se il coefficiente è significativo ---
                        if abs(float(coeff_frac)) > NUMERICAL_TOLERANCE:
                            cut_indices.append(non_basic_var_name)
                            cut_coeffs.append(float(coeff_frac))

                    if cut_indices:
                        generated_cuts.append({
                            'indices': cut_indices,
                            'coeffs': cut_coeffs,
                            'rhs': float(f_i_frac),
                            'sense': 'G',
                            'violation': float(f_i_frac)
                        })
        except cplex.CplexError as e:
            print(f"ERRORE CPLEX durante la generazione dei tagli GMI: {e}")
        return generated_cuts

        #metodo principale di risoluzione

    def solve_problem(self, instance_path_str: str, cut_mode: str):
        instance_path = Path(instance_path_str)
        name = instance_path.stem

        c, A, b = self.solver.get_problem_data(maximize=False)
        self.n_cols_original, n_rows = len(c), len(b)

        optimal_sol = self.solver.determine_optimal(instance_path, maximize=False)
        if optimal_sol is None: return []

        tot_stats = []
        try:
            with cplex.Cplex() as mkp:
                # 1. Setup del problema LP iniziale
                mkp.set_problem_type(mkp.problem_type.LP)
                mkp.set_problem_name(name + "_LP_Relaxation")
                mkp.objective.set_sense(mkp.objective.sense.minimize)
                mkp.parameters.preprocessing.presolve.set(0)
                mkp.parameters.lpmethod.set(mkp.parameters.lpmethod.values.primal)

                var_names = [f"x{i}" for i in  range(self.n_cols_original)]
                mkp.variables.add(obj=c, lb=[0.0] * self.n_cols_original, ub=[1.0] * self.n_cols_original, names=var_names)
                mkp.linear_constraints.add(
                    lin_expr=[cplex.SparsePair(ind=list(range(self.n_cols_original)), val=A[i]) for i in range(n_rows)],
                    rhs=b.tolist(), senses=['L'] * n_rows, names=[f"c{i}" for i in range(n_rows)]
                )

                # 2. Risoluzione del rilassamento LP iniziale
                start_time = datetime.datetime.now()
                mkp.solve()
                sol, sol_type, status = print_solution(mkp)
                elapsed_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
                stats_iter_0 = get_statistics(name, self.n_cols_original, n_rows, optimal_sol, sol, sol_type, status, 0, elapsed_time, 0)
                tot_stats.append(stats_iter_0)

                if status != 'optimal':
                    print("ERRORE: Rilassamento iniziale non risolto ottimamente.")
                    return tot_stats

                # 3. Ciclo iterativo di aggiunta dei tagli
                iteration, total_time, num_total_cuts = 1, elapsed_time, 0
                MAX_TOTAL_CUTS = 500 # Limite di sicurezza sul numero totale di tagli

                while (total_time <= TIME_LIMIT and num_total_cuts <= MAX_TOTAL_CUTS and
                       modulus(sol, optimal_sol) / (abs(optimal_sol) + 1e-6) > THRESHOLD_GAP and
                       status == "optimal" and iteration <= MAX_ITERATIONS):

                    start_iteration_time = datetime.datetime.now()

                    # 3a. Genera i tagli usando i metodi della classe
                    cuts_to_process = []
                    if cut_mode == 'GFC':
                        cuts_to_process = self._generate_gomory_fractional_cuts(mkp)
                    elif cut_mode == 'GMI':
                        cuts_to_process = self._generate_gomory_mixed_integer_cuts(mkp)
                    elif cut_mode == 'BEST':
                        cuts_gmi= self._generate_gomory_mixed_integer_cuts(mkp)
                        cuts_gfc = self._generate_gomory_fractional_cuts(mkp)
                        # Combina i migliori tagli da entrambi i metodi invece di scegliere un solo tipo
                        cuts_gmi.sort(key=lambda x: x.get('violation', 0), reverse=True)
                        cuts_gfc.sort(key=lambda x: x.get('violation', 0), reverse=True)

                        len_gmi = len(cuts_gmi)
                        len_gfc = len(cuts_gmi)
                        max_len= max(len_gmi, len_gfc)
                        for i in range(max_len):
                            if i < len_gmi:
                                cuts_to_process.append(cuts_gmi[i])
                            if i < len_gfc:
                                cuts_to_process.append(cuts_gfc[i])


                    if not cuts_to_process:
                        print("STOP: Nessun nuovo taglio generato.")
                        break

                    # 3b. Seleziona i tagli migliori e aggiungili
                    cuts_to_process.sort(key=lambda x: (
                        x.get('violation', 0)  # Secondo criterio: "forza" del taglio
                    ), reverse=True)

                    cuts_added_this_iteration = 0




                    print(f"Iterazione {iteration}: Aggiungendo {len(cuts_to_process)} nuovi tagli (tipo: {cut_mode}).")


                    for i, cut_info in enumerate(cuts_to_process):

                        cut_name=f"{cut_mode.lower()}_{iteration}_{i}"
                        mkp.linear_constraints.add(
                            lin_expr=[cplex.SparsePair(ind=cut_info['indices'], val=cut_info['coeffs'])],
                            senses=[cut_info['sense']], rhs=[cut_info['rhs']],
                            names=[cut_name]
                        )

                        # 3c. Risolvi il modello aggiornato
                        mkp.solve()

                        current_sol, _, current_status = print_solution(mkp)
                        if current_status != 'optimal' or current_sol > optimal_sol + NUMERICAL_TOLERANCE:
                            print(f"AVVISO: Il taglio {i+1} ha causato instabilità.")
                            mkp.linear_constraints.delete(cut_name)

                        else:
                            sol= current_sol
                            cuts_added_this_iteration += 1
                            print(f"  -> Taglio {i+1} (viol: {cut_info['violation']:.4f}) stabile. Aggiunto. Nuova sol: {sol:.4f}")
                    num_total_cuts += cuts_added_this_iteration
                    current_stats = get_statistics(name, self.n_cols_original, n_rows + num_total_cuts, optimal_sol, sol, sol_type, status, num_total_cuts, total_time, iteration)
                    tot_stats.append(current_stats)
                    if cuts_added_this_iteration == 0 :
                        print("STOP: Nessun taglio valido aggiunto in questa iterazione.")
                        break

                    # 3d. Raccogli statistiche
                    iteration_time = (datetime.datetime.now() - start_iteration_time).total_seconds() * 1000
                    total_time += iteration_time
                    iteration += 1


                print(f"\n=== FINE RISOLUZIONE (MODALITÀ {cut_mode}) ===")
                return tot_stats

        except cplex.CplexError as e:
            print(f"ERRORE CPLEX in solve_problem: {e}")
            return tot_stats
        except Exception as e:
            print(f"ERRORE IMPREVISTO in solve_problem: {e}")
            raise