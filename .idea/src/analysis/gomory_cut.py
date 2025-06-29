import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from facilityLocation import FacilityLocationModel
from amplpy import AMPL
from pathlib import Path
import math
import amplpy
from ampl_solver import UFLSolver


class GomoryCut:
    def __init__(self, n_facilities, n_customers, fixed_cost, allocation_cost, ampl_path=None):
        """
        Inizializza il problema UFL

        Args:
            n_facilities: numero di facility
            n_customers: numero di clienti
            fixed_cost: array dei costi fissi per aprire le facility
            allocation_cost: matrice dei costi di allocazione [facility][customer]
            ampl_path: percorso per AMPL (opzionale)
        """
        self.n_facilities = n_facilities
        self.n_customers = n_customers
        self.fixed_cost = np.array(fixed_cost)
        self.allocation_cost = np.array(allocation_cost)

        # Verifica e correggi le dimensioni se necessario
        if self.allocation_cost.shape == (n_customers, n_facilities):
            self.allocation_cost = self.allocation_cost.T

        # Verifica finale delle dimensioni
        if self.fixed_cost.shape[0] != n_facilities:
            raise ValueError(f"fixed_cost deve avere {n_facilities} elementi, ma ne ha {self.fixed_cost.shape[0]}")

        if self.allocation_cost.shape != (n_facilities, n_customers):
            raise ValueError(f"allocation_cost deve essere {n_facilities}x{n_customers} (facilities x customers), ma è {self.allocation_cost.shape}")

        # Crea un modello FacilityLocationModel per compatibilità con UFLSolver
        # NOTA: Passiamo allocation_cost nella forma che si aspetta FacilityLocationModel
        try:
            self.model = FacilityLocationModel(
                num_facilities=n_facilities,
                num_customers=n_customers,
                fixed_costs=self.fixed_cost.tolist(),
                assignment_costs=self.allocation_cost.T.tolist()  # Trasposizione per FacilityLocationModel
            )
        except Exception as e:
            print(f"Errore nella creazione del modello: {e}")
            # Fallback: usa MockFacilityModel
            self.model = self._create_mock_facility_model()

        # Inizializza UFLSolver invece di AMPL direttamente
        self.solver = UFLSolver(ampl_path)
        self.ampl = self.solver.ampl  # Accesso diretto ad AMPL se necessario
        self.cut_counter = 0

        # Setup del modello utilizzando UFLSolver
        self._setup_model_with_solver()

    def _create_mock_facility_model(self):
        """Crea un oggetto MockFacilityModel dai dati"""
        class MockFacilityModel:
            def __init__(self, n_facilities, n_customers, fixed_costs, allocation_costs):
                self.n_facilities = n_facilities
                self.n_customers = n_customers
                # Converti numpy arrays in liste per evitare problemi
                self.fixed_costs = fixed_costs.tolist() if hasattr(fixed_costs, 'tolist') else list(fixed_costs)
                self.allocation_costs = allocation_costs.tolist() if hasattr(allocation_costs, 'tolist') else allocation_costs

            def get_num_facilities(self):
                return self.n_facilities

            def get_num_customers(self):
                return self.n_customers

            def get_fixed_costs(self):
                return self.fixed_costs

            def get_assignment_costs(self):
                # Ritorna come lista di liste [customer][facility] per compatibilità con UFLSolver
                # Converti numpy array in lista per evitare problemi con la valutazione booleana
                if isinstance(self.allocation_costs, list):
                    # Se è già una lista di liste, trasponi
                    return list(map(list, zip(*self.allocation_costs)))
                else:
                    # Se è un array numpy, converti e trasponi
                    return np.array(self.allocation_costs).T.tolist()

        return MockFacilityModel(self.n_facilities, self.n_customers,
                                 self.fixed_cost, self.allocation_cost)

    def _setup_model_with_solver(self):
        """Setup del modello utilizzando UFLSolver"""
        try:
            # Carica il modello utilizzando UFLSolver
            self.solver.load_instance_from_model(self.model)
            print("Modello UFL caricato con successo tramite UFLSolver")
        except Exception as e:
            print(f"Errore nel setup del modello con UFLSolver: {e}")
            raise

    def _solve_lp_relaxation(self) -> Tuple[bool, float, Dict]:
        """Risolve il rilassamento lineare del problema usando UFLSolver"""
        try:

            # Risolvi utilizzando il metodo di UFLSolver
            self.ampl.solve()

            # Controlla il risultato
            solve_result = self.ampl.get_value('solve_result')
            if solve_result != 'solved':
                return False, float('inf'), {}

            # Estrai la soluzione usando la nomenclatura del modello UFL2.mod
            obj_value = self.ampl.get_objective('TotalCost').value()

            solution = {}

            # Variabili x (facilities) - nel UFL2.mod x[u] rappresenta le facility
            x_values = self.ampl.get_variable('x')
            for i in range(self.n_facilities):
                solution[f'y_{i}'] = x_values[i+1].value()  # Mappiamo x[u] -> y_{i} per compatibilità

            # Variabili y (allocazioni) - nel UFL2.mod y[u,v] rappresenta le allocazioni
            y_values = self.ampl.get_variable('y')
            for i in range(self.n_facilities):
                for j in range(self.n_customers):
                    solution[f'x_{i}_{j}'] = y_values[i+1, j+1].value()  # Mappiamo y[u,v] -> x_{i}_{j} per compatibilità

            return True, obj_value, solution

        except Exception as e:
            print(f"Errore nella risoluzione LP: {e}")
            return False, float('inf'), {}

    def _is_integer_solution(self, solution: Dict, tolerance=1e-6) -> bool:
        """Verifica se la soluzione è intera"""
        for var_name, value in solution.items():
            if value is not None and abs(value - round(value)) > tolerance:
                return False
        return True

    def _find_most_fractional_var(self, solution: Dict) -> Optional[str]:
        """Trova la variabile più frazionaria (più vicina a 0.5)"""
        max_fract = 0
        best_var = None

        for var_name, value in solution.items():
            if value is not None:
                fract_part = abs(value - math.floor(value) - 0.5)
                if abs(value - round(value)) > 1e-6 and fract_part < 0.5 - max_fract:
                    max_fract = 0.5 - fract_part
                    best_var = var_name

        return best_var

    def _add_gomory_cut(self, solution: Dict, var_name: str) -> bool:
        """Aggiunge un taglio di Gomory per la variabile specificata"""
        if var_name not in solution:
            return False

        value = solution[var_name]
        if value is None:
            return False

        fract_part = value - math.floor(value)
        if fract_part < 1e-6:
            return False

        self.cut_counter += 1

        # Crea il nome del vincolo
        cut_name = f"gomory_cut_{self.cut_counter}"

        try:
            # Adatta i nomi delle variabili al modello UFL2.mod
            if var_name.startswith('y_'):
                i = int(var_name.split('_')[1]) + 1  # AMPL usa indici 1-based
                # Nel UFL2.mod x[u] rappresenta le facility
                constraint = f"subject to {cut_name}: x[{i}] <= {math.floor(value)};"
            else:  # x_i_j (allocazioni)
                parts = var_name.split('_')
                i, j = int(parts[1]) + 1, int(parts[2]) + 1  # AMPL usa indici 1-based
                # Nel UFL2.mod y[u,v] rappresenta le allocazioni
                constraint = f"subject to {cut_name}: y[{i},{j}] <= {math.floor(value)};"

            self.ampl.eval(constraint)
            return True

        except Exception as e:
            print(f"Errore nell'aggiungere il taglio: {e}")
            return False

    def solve_with_gomory_cuts(self, max_iterations, tolerance)-> Dict:
        """
        Risolve il problema UFL utilizzando i tagli di Gomory

        Args:
            max_iterations: numero massimo di iterazioni
            tolerance: tolleranza per considerare una soluzione intera

        Returns:
            dict con la soluzione e le informazioni del processo
        """
        iteration = 0
        cut_count = 0
        obj_history=[]
        cut_history=[]

        print("Inizio risoluzione con tagli di Gomory...")
        print(f"Problema: {self.n_facilities} facility, {self.n_customers} clienti")

        while iteration < max_iterations:
            iteration += 1

            # Risolvi il rilassamento lineare
            success, obj_value, solution = self._solve_lp_relaxation()

            if not success:
                print(f"Errore nella risoluzione all'iterazione {iteration}")
                break

            print(f"Iterazione {iteration}: Valore obiettivo = {obj_value:.4f}")

            # Verifica se la soluzione è intera
            if self._is_integer_solution(solution, tolerance):
                print(f"Soluzione intera trovata dopo {iteration} iterazioni e {cut_count} tagli!")

                # Estrai le facility aperte
                open_facilities = []
                for i in range(self.n_facilities):
                    if solution[f'y_{i}'] > 0.5:
                        open_facilities.append(i)

                # Estrai le allocazioni
                allocations = {}
                for j in range(self.n_customers):
                    for i in range(self.n_facilities):
                        if solution[f'x_{i}_{j}'] > 0.5:
                            allocations[j] = i
                            break

                result = {
                    'success': True,
                    'optimal_value': obj_value,
                    'open_facilities': open_facilities,
                    'allocations': allocations,
                    'iterations': iteration,
                    'cuts_added': cut_count,
                    'solution': solution,
                    'obj_values': obj_history,
                    'cuts': cut_history
                }
                return result

            # Trova la variabile più frazionaria e aggiungi un taglio
            fract_var = self._find_most_fractional_var(solution)

            if fract_var is None:
                print("Nessuna variabile frazionaria trovata, ma la soluzione non è intera.")
                break

            if self._add_gomory_cut(solution, fract_var):
                cut_count += 1
                value = solution[fract_var]
                print(f"  Aggiunto taglio di Gomory per {fract_var} (valore: {value:.6f} -> <= {math.floor(value)})")
            else:
                print("Impossibile aggiungere ulteriori tagli di Gomory")
                break
            obj_history.append(obj_value)
            cut_history.append(cut_count)
        print(f"Raggiunto limite di iterazioni ({max_iterations})")
        result = {
            'success': False,
            'message': 'Limite di iterazioni raggiunto',
            'iterations': iteration,
            'cuts_added': cut_count,
            'last_objective': obj_value if 'obj_value' in locals() else None,
            'obj_values': obj_history,
            'cuts': cut_history
        }
        return result



    def print_solution(self, solution_info: Dict,filename):
        """Stampa i dettagli della soluzione"""
        if not solution_info['success']:
            print("Soluzione non trovata:", solution_info.get('message', 'Errore sconosciuto'))
            return

        print("\n" + "="*60)
        print("SOLUZIONE OTTIMA TROVATA (Tagli di Gomory)")
        print("="*60)
        print(f"Valore obiettivo: {solution_info['optimal_value']:.6f}")
        print(f"Iterazioni: {solution_info['iterations']}")
        print(f"Tagli di Gomory aggiunti: {solution_info['cuts_added']}")

        print(f"\nFacility aperte ({len(solution_info['open_facilities'])}): {solution_info['open_facilities']}")

        # Calcola i costi
        total_fixed_cost = sum(self.fixed_cost[i] for i in solution_info['open_facilities'])
        total_allocation_cost = sum(self.allocation_cost[facility][customer]
                                    for customer, facility in solution_info['allocations'].items())
        z_opt=self.solver.load_optimal_solution(filename)
        self.solver.compare_with_optimal(filename,total_allocation_cost+total_fixed_cost ,z_opt)
        print(f"\nDettaglio costi:")
        print(f"  Costo fisso totale: {total_fixed_cost:.2f}")
        print(f"  Costo allocazione totale: {total_allocation_cost:.2f}")
        print(f"  Costo totale: {total_fixed_cost + total_allocation_cost:.2f}")

    def close(self):
        """Chiude la sessione AMPL"""
        self.ampl.close()


# Esempio di utilizzo


