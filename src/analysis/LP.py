import numpy as np
from fractions import Fraction
from typing import Dict, List, Tuple, Optional, Union
import logging
from dataclasses import dataclass

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SimplexResult:
    """Classe per i risultati del metodo del simplesso"""
    table: np.ndarray
    optimal: bool
    unbounded: bool
    alternate: bool
    iterations: int
    objective_value: float


class Simplex:
    """Classe migliorata per il metodo del simplesso con supporto per i tagli di Gomory"""

    def __init__(self, A: np.ndarray, b: np.ndarray, c: np.ndarray,
                 tableau_method: str = "standard"):
        """
        Inizializza il solver del simplesso

        Args:
            A: Matrice dei vincoli
            b: Vettore dei termini noti
            c: Vettore dei coefficienti della funzione obiettivo
            tableau_method: Metodo per creare il tableau ("standard" o "big_m")
        """
        self.original_A = A.copy()
        self.original_b = b.copy()
        self.original_c = c.copy()
        self.tableau_method = tableau_method

        # Prepara il problema in forma standard
        self.A, self.b, self.c = self._prepare_standard_form(A, b, c)
        self.num_vars = len(self.c)
        self.num_constraints = len(self.b)

        # Variabili per tenere traccia delle iterazioni
        self.iteration_count = 0
        self.max_iterations = 1000

    def _prepare_standard_form(self, A: np.ndarray, b: np.ndarray, c: np.ndarray) -> Tuple[
        np.ndarray, np.ndarray, np.ndarray]:
        """Converte il problema in forma standard aggiungendo variabili slack"""
        # Aggiungi variabili slack per vincoli <=
        m, n = A.shape

        # Matrice identità per le variabili slack
        slack_matrix = np.eye(m)

        # Nuova matrice A con variabili slack
        A_standard = np.hstack([A, slack_matrix])

        # Nuovo vettore c con coefficienti 0 per le variabili slack
        c_standard = np.hstack([c, np.zeros(m)])

        return A_standard, b.copy(), c_standard

    def _create_initial_tableau(self) -> np.ndarray:
        """Crea il tableau iniziale del simplesso"""
        m, n = self.A.shape

        # Identifica le variabili di base iniziali (variabili slack)
        basic_vars = list(range(n - m, n))

        # Crea il tableau: [B | cb | xb | A]
        tableau = np.zeros((m, n + 3))

        for i, var in enumerate(basic_vars):
            tableau[i, 0] = var  # Indice della variabile di base
            tableau[i, 1] = self.c[var]  # Coefficiente nella funzione obiettivo
            tableau[i, 2] = self.b[i]  # Valore della variabile di base
            tableau[i, 3:] = self.A[i, :]  # Riga dei vincoli

        return tableau

    def _is_optimal(self, tableau: np.ndarray) -> bool:
        """Controlla se la soluzione corrente è ottimale"""
        for j in range(len(self.c)):
            zj = np.sum(tableau[:, 1] * tableau[:, 3 + j])
            reduced_cost = zj - self.c[j]
            if reduced_cost < -1e-10:  # Tolleranza numerica
                return False
        return True

    def _find_entering_variable(self, tableau: np.ndarray) -> int:
        """Trova la variabile entrante (regola di Bland per evitare cicli)"""
        for j in range(len(self.c)):
            zj = np.sum(tableau[:, 1] * tableau[:, 3 + j])
            reduced_cost = zj - self.c[j]
            if reduced_cost < -1e-10:
                return j
        return -1

    def _find_leaving_variable(self, tableau: np.ndarray, entering_var: int) -> int:
        """Trova la variabile uscente usando il test del rapporto minimo"""
        min_ratio = float('inf')
        leaving_var = -1

        for i in range(len(tableau)):
            if tableau[i, 3 + entering_var] > 1e-10:  # Elemento positivo
                ratio = tableau[i, 2] / tableau[i, 3 + entering_var]
                if ratio >= 0 and ratio < min_ratio:
                    min_ratio = ratio
                    leaving_var = i

        return leaving_var

    def _pivot(self, tableau: np.ndarray, pivot_row: int, pivot_col: int):
        """Esegue l'operazione di pivot"""
        pivot_element = tableau[pivot_row, 3 + pivot_col]

        # Normalizza la riga del pivot
        tableau[pivot_row, 2:] /= pivot_element

        # Elimina gli altri elementi della colonna del pivot
        for i in range(len(tableau)):
            if i != pivot_row and abs(tableau[i, 3 + pivot_col]) > 1e-10:
                multiplier = tableau[i, 3 + pivot_col]
                tableau[i, 2:] -= multiplier * tableau[pivot_row, 2:]

        # Aggiorna la variabile di base
        tableau[pivot_row, 0] = pivot_col
        tableau[pivot_row, 1] = self.c[pivot_col]

    def solve(self, verbose: bool = True) -> SimplexResult:
        """Risolve il problema usando il metodo del simplesso"""
        tableau = self._create_initial_tableau()

        self.iteration_count = 0

        while self.iteration_count < self.max_iterations:
            if self._is_optimal(tableau):
                if verbose:
                    print("Soluzione ottimale trovata!")
                break

            entering_var = self._find_entering_variable(tableau)
            if entering_var == -1:
                break

            leaving_var = self._find_leaving_variable(tableau, entering_var)
            if leaving_var == -1:
                if verbose:
                    print("Problema non limitato!")
                return SimplexResult(tableau, False, True, False,
                                     self.iteration_count, float('inf'))


            self._pivot(tableau, leaving_var, entering_var)
            self.iteration_count += 1


        # Calcola il valore della funzione obiettivo
        obj_value = np.sum(tableau[:, 1] * tableau[:, 2])

        return SimplexResult(tableau, True, False, False,
                             self.iteration_count, obj_value)

    def get_solution(self, tableau: np.ndarray) -> Dict[str, Union[float, List[float]]]:
        """Estrae la soluzione dal tableau finale"""
        solution = np.zeros(len(self.original_c))

        for i in range(len(tableau)):
            var_index = int(tableau[i, 0])
            if var_index < len(self.original_c):
                solution[var_index] = tableau[i, 2]

        obj_value = np.sum(tableau[:, 1] * tableau[:, 2])

        return {
            'objective_value': obj_value,
            'variables': solution.tolist(),
            'basic_variables': [int(row[0]) for row in tableau],
            'basic_values': [row[2] for row in tableau]
        }
