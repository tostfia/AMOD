import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from facilityLocation import FacilityLocationModel
from amplpy import AMPL
from pathlib import Path
from ampl_solver import UFLSolver
import math
import amplpy



class GomoryCut:
    def __init__(self, n_facilities, n_customers, fixed_cost, allocation_cost):
        """
        Inizializza il problema UFL

        Args:
            n_facilities: numero di facility
            n_customers: numero di clienti
            fixed_cost: array dei costi fissi per aprire le facility
            allocation_cost: matrice dei costi di allocazione [facility][customer]
        """
        self.n_facilities = n_facilities
        self.n_customers = n_customers
        self.fixed_cost = np.array(fixed_cost)
        self.allocation_cost = np.array(allocation_cost)
        # Verifica e correggi le dimensioni se necessario
        if self.allocation_cost.shape == (n_customers, n_facilities):
            print(f"Attenzione: allocation_cost ha dimensioni ({n_customers}, {n_facilities}), trasposizione automatica a ({n_facilities}, {n_customers})")
            self.allocation_cost = self.allocation_cost.T

        # Verifica finale delle dimensioni
        if self.fixed_cost.shape[0] != n_facilities:
            raise ValueError(f"fixed_cost deve avere {n_facilities} elementi, ma ne ha {self.fixed_cost.shape[0]}")

        if self.allocation_cost.shape != (n_facilities, n_customers):
            raise ValueError(f"allocation_cost deve essere {n_facilities}x{n_customers} (facilities x customers), ma è {self.allocation_cost.shape}")
        self.n_vars = n_facilities + n_facilities * n_customers

        # Inizializzo AMPL
        self.ampl = amplpy.AMPL()
        self.cut_counter = 0
        self.model=FacilityLocationModel(
            num_facilities=n_facilities,
            num_customers=n_customers,
            fixed_costs=fixed_cost,
            assignment_costs=allocation_cost
        )
        self._setup_problem(self.model)


    def _setup_problem(self,model)->Tuple[bool,float,Dict]:
        """Setup del problema di programmazione lineare rilassato"""
        solver=UFLSolver()
        solver.load_instance_from_model(model)
        try:
            self.ampl.solve()
            if self.ampl.solve_result != 'solved':
                return False, float('inf'), {}

            # Estrai la soluzione
            obj_value = solver.solve_instance(model)

            solution = {}

            # Variabili y (facilities)
            for i in range(self.n_facilities):
                solution[f'y_{i}'] = self.ampl.var['y'][i+1].value()

            # Variabili x (allocazioni)
            for i in range(self.n_facilities):
                for j in range(self.n_customers):
                    solution[f'x_{i}_{j}'] = self.ampl.var['x'][i+1, j+1].value()

            return True, obj_value, solution

        except Exception as e:
            print(f"Errore nella risoluzione: {e}")
            return False, float('inf'), {}



    def _is_integer_solution(self, solution:Dict, tolerance=1e-6)->bool:
        """Verifica se la soluzione è intera"""
        for var_name, value in solution.items():
            if value is not None and abs(value - round(value)) > tolerance:
                return False
        return True

    def _find_most_fractional_var(self, solution:Dict) -> Optional[str]:
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
    def _add_gomory_cut(self, solution, var_idx):
        """Aggiunge un taglio di Gomory per la variabile specificata"""
        value = solution[var_name]
        if value is None:
            return False

        fract_part = value - math.floor(value)
        if fract_part < 1e-6:
            return False

        self.cut_counter += 1

        # Crea il nome del vincolo
        cut_name = f"gomory_cut_{self.cut_counter}"

        # Determina il tipo di variabile e crea il taglio
        if var_name.startswith('y_'):
            i = int(var_name.split('_')[1]) + 1  # AMPL usa indici 1-based
            # Aggiungi vincolo: y[i] <= floor(value)
            constraint = f"subject to {cut_name}: y[{i}] <= {math.floor(value)};"
        else:  # x_i_j
            parts = var_name.split('_')
            i, j = int(parts[1]) + 1, int(parts[2]) + 1  # AMPL usa indici 1-based
            # Aggiungi vincolo: x[i,j] <= floor(value)
            constraint = f"subject to {cut_name}: x[{i},{j}] <= {math.floor(value)};"

        try:
            self.ampl.eval(constraint)
            return True
        except Exception as e:
            print(f"Errore nell'aggiungere il taglio: {e}")
            return False

    def solve_with_gomory_cuts(self, max_iterations, tolerance):
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

        print("Inizio risoluzione con tagli di Gomory...")
        print(f"Problema: {self.n_facilities} facility, {self.n_customers} clienti")

        while iteration < max_iterations:
            iteration += 1

            # Risolvi il problema lineare rilassato
            success, obj_value, solution = self._setup_problem(self.model)

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

                return {
                    'success': True,
                    'optimal_value': obj_value,
                    'open_facilities': open_facilities,
                    'allocations': allocations,
                    'iterations': iteration,
                    'cuts_added': cut_count,
                    'solution': solution
                }

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

        print(f"Raggiunto limite di iterazioni ({max_iterations})")
        return {
            'success': False,
            'message': 'Limite di iterazioni raggiunto',
            'iterations': iteration,
            'cuts_added': cut_count,
            'last_objective': obj_value if 'obj_value' in locals() else None
        }

    def print_solution(self, solution_info: Dict):
        """Stampa i dettagli della soluzione"""
        if not solution_info['success']:
            print("Soluzione non trovata:", solution_info.get('message', 'Errore sconosciuto'))
            return

        print("\n" + "="*60)
        print("SOLUZIONE OTTIMA TROVATA (AMPL)")
        print("="*60)
        print(f"Metodo: {solution_info.get('method', 'Tagli di Gomory')}")
        print(f"Valore obiettivo: {solution_info['optimal_value']:.6f}")

        if 'iterations' in solution_info:
            print(f"Iterazioni: {solution_info['iterations']}")
        if 'cuts_added' in solution_info:
            print(f"Tagli di Gomory aggiunti: {solution_info['cuts_added']}")

        print(f"\nFacility aperte ({len(solution_info['open_facilities'])}): {solution_info['open_facilities']}")

        # Calcola i costi
        total_fixed_cost = sum(self.fixed_cost[i] for i in solution_info['open_facilities'])
        total_allocation_cost = sum(self.allocation_cost[facility][customer]
                                    for customer, facility in solution_info['allocations'].items())

        print(f"\nDettaglio costi:")
        print(f"  Costo fisso totale: {total_fixed_cost:.2f}")
        print(f"  Costo allocazione totale: {total_allocation_cost:.2f}")
        print(f"  Costo totale: {total_fixed_cost + total_allocation_cost:.2f}")

    def close(self):
        """Chiude la sessione AMPL"""
        self.ampl.close()