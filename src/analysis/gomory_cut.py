from typing import Dict, List, Tuple, Optional, Union
import numpy as np
from analysis.LP import *


class GomoryCut:
    """Classe migliorata per i tagli di Gomory"""

    def __init__(self, A: np.ndarray, b: np.ndarray, c: np.ndarray):
        """
        Inizializza il solver con tagli di Gomory

        Args:
            A: Matrice dei vincoli del problema originale
            b: Vettore dei termini noti
            c: Vettore dei coefficienti della funzione obiettivo
        """
        self.original_A = A.copy()
        self.original_b = b.copy()
        self.original_c = c.copy()

        # Variabili per tenere traccia dei tagli aggiunti
        self.current_A = A.copy()
        self.current_b = b.copy()
        self.current_c = c.copy()
        self.cuts_added = []

        self.tolerance = 1e-6

    def _is_integer(self, value: float, tolerance: float = 1e-6) -> bool:
        """Controlla se un valore è intero entro una tolleranza"""
        return abs(value - round(value)) < tolerance

    def _find_fractional_variable(self, tableau: np.ndarray) -> Tuple[int, float]:
        """
        Trova una variabile con valore frazionario

        Returns:
            Tupla (indice_riga, valore_frazionario) o (-1, 0) se tutte sono intere
        """
        max_fractional = 0
        best_row = -1

        for i in range(len(tableau)):
            var_index = int(tableau[i, 0])
            value = tableau[i, 2]

            # Considera solo le variabili originali del problema
            if var_index < len(self.original_c):
                fractional_part = abs(value - round(value))
                if fractional_part > self.tolerance and fractional_part > max_fractional:
                    max_fractional = fractional_part
                    best_row = i

        return (best_row, max_fractional) if best_row != -1 else (-1, 0)

    def _generate_gomory_cut(self, tableau: np.ndarray, row_index: int) -> Tuple[np.ndarray, float]:
        """
        Genera un taglio di Gomory dalla riga specificata

        Args:
            tableau: Tableau corrente
            row_index: Indice della riga da cui generare il taglio

        Returns:
            Tupla (coefficienti_taglio, termine_noto_taglio)
        """
        row = tableau[row_index, :]

        # Valore della variabile di base (parte frazionaria)
        basic_value = row[2]
        f0 = basic_value - int(basic_value)  # Parte frazionaria

        # Coefficienti del taglio
        cut_coefficients = np.zeros(len(self.current_c))

        for j in range(len(self.current_c)):
            coeff = row[3 + j]
            fj = coeff - int(coeff)  # Parte frazionaria del coefficiente
            cut_coefficients[j] = -fj

        return cut_coefficients, -f0

    def _add_cut_to_problem(self, cut_coefficients: np.ndarray, cut_rhs: float):
        """Aggiunge un taglio al problema corrente"""
        # Aggiungi una nuova riga alla matrice A
        new_row = np.hstack([cut_coefficients, [1]])  # Aggiungi variabile slack
        self.current_A = np.vstack([self.current_A, new_row])

        # Aggiungi il termine noto
        self.current_b = np.hstack([self.current_b, [cut_rhs]])

        # Aggiungi coefficiente 0 per la nuova variabile slack nella funzione obiettivo
        self.current_c = np.hstack([self.current_c, [0]])

        # Salva il taglio aggiunto
        self.cuts_added.append({
            'coefficients': cut_coefficients.copy(),
            'rhs': cut_rhs,
            'iteration': len(self.cuts_added) + 1
        })

        logger.info(f"Taglio {len(self.cuts_added)} aggiunto: {cut_coefficients} >= {cut_rhs}")

    def solve_with_gomory_cuts(self, max_iterations: int = 10, verbose: bool = True) -> Optional[Dict]:
        """
        Risolve il problema UFL con tagli di Gomory

        Args:
            max_iterations: Numero massimo di iterazioni
            verbose: Se stampare informazioni dettagliate

        Returns:
            Dizionario con i risultati della soluzione
        """
        iteration = 0

        while iteration < max_iterations:
            if verbose:
                print(f"\n{'=' * 50}")
                print(f"ITERAZIONE GOMORY {iteration + 1}")
                print(f"{'=' * 50}")

            # Risolvi il rilassamento lineare corrente
            simplex_solver = Simplex(self.current_A, self.current_b, self.current_c)
            result = simplex_solver.solve(verbose=verbose)

            if not result.optimal:
                logger.error("Impossibile risolvere il rilassamento lineare")
                return None

            # Controlla se tutte le variabili sono intere
            row_index, fractional_value = self._find_fractional_variable(result.table)

            if row_index == -1:
                if verbose:
                    print("\n🎉 SOLUZIONE OTTIMA INTERA TROVATA!")
                    print(f"Valore ottimo: {result.objective_value}")

                # Estrai la soluzione finale
                solution = simplex_solver.get_solution(result.table)

                return {
                    'objective_value': solution['objective_value'],
                    'variables': solution['variables'],
                    'iterations': iteration + 1,
                    'cuts_added': len(self.cuts_added),
                    'optimal': True,
                    'tableau': result.table,
                    'cuts_history': self.cuts_added.copy()
                }

            if verbose:
                var_idx = int(result.table[row_index, 0])
                var_value = result.table[row_index, 2]
                print(f"\n🔍 Variabile frazionaria trovata: x{var_idx} = {var_value}")
                print(f"Parte frazionaria: {fractional_value:.6f}")

            # Genera e aggiungi un taglio di Gomory
            cut_coefficients, cut_rhs = self._generate_gomory_cut(result.table, row_index)
            self._add_cut_to_problem(cut_coefficients, cut_rhs)

            iteration += 1

        if verbose:
            print(f"\n⚠️  Raggiunto il limite massimo di iterazioni ({max_iterations})")

        # Restituisci la migliore soluzione trovata
        simplex_solver = Simplex(self.current_A, self.current_b, self.current_c)
        result = simplex_solver.solve(verbose=False)
        solution = simplex_solver.get_solution(result.table)

        return {
            'objective_value': result.objective_value,
            'variables': solution['variables'],
            'iterations': max_iterations,
            'cuts_added': len(self.cuts_added),
            'optimal': False,
            'tableau': result.table,
            'cuts_history': self.cuts_added.copy()
        }
