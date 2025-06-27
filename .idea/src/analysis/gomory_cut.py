from typing import Dict, List, Tuple, Optional
import numpy as np
from dataclasses import dataclass
import logging

@dataclass
class CutInfo:
    """Informazioni su un taglio di Gomory"""
    coefficients: Dict[int, float]
    rhs: float
    iteration: int
    fractional_value: float

class GomoryCut:
    """Implementazione migliorata dei tagli di Gomory per problemi UFL"""

    def __init__(self, ampl_solver: 'UFLSolver', max_iterations: int = 50, tolerance: float = 1e-6):
        self.ampl_solver = ampl_solver
        self.ampl = ampl_solver.ampl
        self.cuts_added = []
        self.iteration_history = []
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.logger = logging.getLogger(__name__)




    def is_integer_solution(self, solution: Dict[int, float]) -> bool:
        """Controlla se la soluzione è intera entro la tolleranza"""
        for value in solution.values():
            if abs(value - round(value)) > self.tolerance:
                return False
        return True

    def find_most_fractional_variable(self, solution: Dict[str, float]) -> Optional[Tuple[str, float]]:
        """
        Trova la variabile con la parte frazionaria più vicina a 0.5
        Returns: (variable_name, fractional_part) o None se tutte sono intere
        """
        max_fractional = 0
        most_fractional_var = None

        for var_name, value in solution.items():
            if var_name.startswith('x['):  # Solo variabili di facility
                fractional_part = abs(value - round(value))
                if fractional_part > self.tolerance and fractional_part > max_fractional:
                    max_fractional = fractional_part
                    most_fractional_var = (var_name, fractional_part)

        return most_fractional_var

    def generate_gomory_cut(self, solution: Dict[str, float]) -> Optional[CutInfo]:
        """
        Genera un taglio di Gomory senza tableau usando metodi alternativi
        """
        # Trova la variabile più frazionaria
        fractional_info = self.find_most_fractional_variable(solution)
        if not fractional_info:
            return None

        var_name, fractional_part = fractional_info
        var_value = solution[var_name]

        # Metodo 1: Taglio frazionario semplice
        return self._generate_fractional_cut(var_name, var_value, solution)

    def _generate_fractional_cut(self, var_name: str, var_value: float, solution: Dict[str, float]) -> CutInfo:
        """
        Genera un taglio frazionario basato sulla variabile più frazionaria
        Questo è più efficace dei semplici bound cuts
        """
        # Estrai l'indice della facility
        facility_id = int(var_name.split('[')[1].split(']')[0])

        # Parte frazionaria della variabile
        fractional_part = var_value - int(var_value)

        # Genera un taglio che coinvolge variabili correlate
        cut_coefficients = {}

        # Coefficiente per la variabile principale
        cut_coefficients[var_name] = 1.0

        # Aggiungi coefficienti per variabili correlate se disponibili
        # (variabili y che dipendono dalla stessa facility)
        correlation_factor = 0.3  # Fattore di correlazione

        for other_var, other_value in solution.items():
            if other_var != var_name and other_var.startswith('x['):
                other_id = int(other_var.split('[')[1].split(']')[0])

                # Se le facilities sono "vicine" (euristica basata sull'ID)
                if abs(facility_id - other_id) <= 2 and other_value > self.tolerance:
                    other_fractional = other_value - int(other_value)
                    if other_fractional > self.tolerance:
                        # Coefficiente basato sulla correlazione
                        coeff = correlation_factor * (other_fractional / fractional_part)
                        cut_coefficients[other_var] = coeff

        # RHS del taglio: parte intera della variabile principale + correzione
        rhs = int(var_value) + max(0, fractional_part - 0.5)

        return CutInfo(
            coefficients=cut_coefficients,
            rhs=rhs,
            iteration=len(self.cuts_added),
            fractional_value=fractional_part
        )

    def _generate_strengthened_cut(self, solution: Dict[str, float]) -> Optional[CutInfo]:
        """
        Genera un taglio rafforzato basato su multiple variabili frazionarie
        """
        # Trova tutte le variabili frazionarie
        fractional_vars = []

        for var_name, value in solution.items():
            if var_name.startswith('x['):
                fractional_part = abs(value - round(value))
                if fractional_part > self.tolerance:
                    fractional_vars.append((var_name, value, fractional_part))

        if len(fractional_vars) < 2:
            return None

        # Ordina per parte frazionaria decrescente
        fractional_vars.sort(key=lambda x: x[2], reverse=True)

        # Prendi le prime 3-5 variabili più frazionarie
        selected_vars = fractional_vars[:min(5, len(fractional_vars))]

        cut_coefficients = {}
        total_fractional = 0

        for var_name, value, frac_part in selected_vars:
            # Coefficiente proporzionale alla parte frazionaria
            coeff = frac_part / sum(v[2] for v in selected_vars)
            cut_coefficients[var_name] = coeff
            total_fractional += frac_part * coeff

        # RHS basato sulla combinazione delle parti frazionarie
        rhs = max(0, total_fractional - 0.5)

        return CutInfo(
            coefficients=cut_coefficients,
            rhs=rhs,
            iteration=len(self.cuts_added),
            fractional_value=max(v[2] for v in selected_vars)
        )

    def _generate_simple_cut(self, var_name: str, var_value: float) -> CutInfo:
        """Genera un taglio semplice quando il tableau non è disponibile"""
        # Estrai l'indice della variabile
        facility_id = int(var_name.split('[')[1].split(']')[0])

        # Taglio semplice: x[i] <= floor(current_value)
        cut_coefficients = {var_name: 1.0}
        rhs = int(var_value)  # floor del valore corrente

        return CutInfo(
            coefficients=cut_coefficients,
            rhs=rhs,
            iteration=len(self.cuts_added),
            fractional_value=abs(var_value - round(var_value))
        )

    def add_gomory_cut(self, cut_info: CutInfo) -> bool:
        """
        Aggiungi un taglio di Gomory al modello AMPL
        """
        try:
            # Costruisci l'espressione del taglio
            cut_expr = " + ".join([
                f"{coeff} * {var}" for var, coeff in cut_info.coefficients.items()
            ])

            # Nome del vincolo
            constraint_name = f"gomory_cut_{cut_info.iteration}"

            # Aggiungi il vincolo ad AMPL
            constraint_def = f"subject to {constraint_name}: {cut_expr} <= {cut_info.rhs};"
            self.ampl.eval(constraint_def)

            # Salva informazioni sul taglio
            self.cuts_added.append(cut_info)

            self.logger.info(f"Aggiunto taglio {constraint_name}: {cut_expr} <= {cut_info.rhs}")
            return True

        except Exception as e:
            self.logger.error(f"Errore nell'aggiunta del taglio: {e}")
            return False

    def solve_with_gomory_cuts(self, model: 'FacilityLocationModel', cut_strategy: str = 'fractional') -> Tuple[float, Dict[int, float], int]:
        """
        Risolvi il problema utilizzando i tagli di Gomory
        cut_strategy: 'simple', 'fractional', 'strengthened', 'mixed'
        Returns: (objective_value, integer_solution, iterations)
        """
        self.cuts_added = []
        self.iteration_history = []

        for iteration in range(self.max_iterations):
            # Risolvi il rilassamento lineare
            obj_value, is_feasible = self.solve_linear_relaxation(model)

            if not is_feasible:
                self.logger.error(f"Problema infeasible all'iterazione {iteration}")
                return float('inf'), {}, iteration

            # Ottieni la soluzione
            full_solution = self.get_optimal_solution()
            facility_solution = self.get_facility_solution()

            # Salva la storia
            self.iteration_history.append({
                'iteration': iteration,
                'objective': obj_value,
                'integer': self.is_integer_solution(facility_solution),
                'num_fractional': sum(1 for v in facility_solution.values()
                                      if abs(v - round(v)) > self.tolerance)
            })

            self.logger.info(f"Iterazione {iteration}: Obiettivo = {obj_value:.4f}, "
                             f"Variabili frazionarie = {self.iteration_history[-1]['num_fractional']}")

            # Controlla se la soluzione è intera
            if self.is_integer_solution(facility_solution):
                self.logger.info(f"Soluzione intera trovata dopo {iteration} iterazioni")
                return obj_value, facility_solution, iteration

            # Genera tagli basati sulla strategia scelta
            cuts_generated = self._generate_cuts_by_strategy(full_solution, cut_strategy)

            if not cuts_generated:
                self.logger.warning("Impossibile generare ulteriori tagli")
                break

            # Aggiungi i tagli generati
            cuts_added = 0
            for cut_info in cuts_generated:
                if self.add_gomory_cut(cut_info):
                    cuts_added += 1

            if cuts_added == 0:
                self.logger.error("Errore nell'aggiunta dei tagli")
                break

            self.logger.info(f"Aggiunti {cuts_added} tagli")

        # Se non abbiamo trovato una soluzione intera
        self.logger.warning(f"Raggiunto limite di iterazioni ({self.max_iterations})")
        facility_solution = self.get_facility_solution()
        return obj_value, facility_solution, self.max_iterations

    def _generate_cuts_by_strategy(self, solution: Dict[str, float], strategy: str) -> List[CutInfo]:
        """Genera tagli basati sulla strategia specificata"""
        cuts = []

        if strategy == 'simple':
            # Genera un taglio semplice
            cut = self._generate_simple_cut_from_solution(solution)
            if cut:
                cuts.append(cut)

        elif strategy == 'fractional':
            # Genera un taglio frazionario
            cut = self.generate_gomory_cut(solution)
            if cut:
                cuts.append(cut)

        elif strategy == 'strengthened':
            # Genera un taglio rafforzato
            cut = self._generate_strengthened_cut(solution)
            if cut:
                cuts.append(cut)

        elif strategy == 'mixed':
            # Combina diverse strategie
            # Prima prova taglio rafforzato
            cut = self._generate_strengthened_cut(solution)
            if cut:
                cuts.append(cut)
            else:
                # Fallback a taglio frazionario
                cut = self.generate_gomory_cut(solution)
                if cut:
                    cuts.append(cut)

        return cuts

    def _generate_simple_cut_from_solution(self, solution: Dict[str, float]) -> Optional[CutInfo]:
        """Genera un taglio semplice dalla soluzione corrente"""
        fractional_info = self.find_most_fractional_variable(solution)
        if not fractional_info:
            return None

        var_name, fractional_part = fractional_info
        var_value = solution[var_name]

        return self._generate_simple_cut(var_name, var_value)

    def get_statistics(self) -> Dict:
        """Ottieni statistiche sull'esecuzione"""
        return {
            'total_cuts': len(self.cuts_added),
            'iterations': len(self.iteration_history),
            'final_objective': self.iteration_history[-1]['objective'] if self.iteration_history else None,
            'integer_found': self.iteration_history[-1]['integer'] if self.iteration_history else False,
            'cuts_info': [
                {
                    'iteration': cut.iteration,
                    'fractional_value': cut.fractional_value,
                    'rhs': cut.rhs
                } for cut in self.cuts_added
            ]
        }

    def reset(self):
        """Reset dello stato del solver"""
        self.cuts_added = []
        self.iteration_history = []

        # Rimuovi i tagli dal modello AMPL
        try:
            for i in range(len(self.cuts_added)):
                self.ampl.eval(f"drop gomory_cut_{i};")
        except:
            pass