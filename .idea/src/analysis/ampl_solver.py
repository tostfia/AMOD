from amplpy import AMPL
from pathlib import Path
class UFLSolver:
    def __init__(self):
        self.ampl = AMPL()

    def load_instance(self, instance_data):
        """Carica i dati dell'istanza UFL"""
        current_path = Path(__file__).parent.parent.parent
        self.ampl.read(current_path/"models"/'UFL.mod')

        # Imposta i parametri
        self.ampl.param['I'] = instance_data['num_facilities']
        self.ampl.param['C'] = instance_data['num_customers']
        self.ampl.param['setup_cost'] = instance_data['fixed_costs']
        self.ampl.param['allocation_cost'] = instance_data['assignment_costs']

    def solve_linear_relaxation(self):
        """Risolve il rilassamento lineare"""
        # Rilassa le variabili binarie
        self.ampl.var['x'].setValues({i: 0 for i in range(1, self.ampl.param['n_facilities'].value() + 1)})
        self.ampl.option['solver'] = 'highs'
        self.ampl.solve()

        return {
            'objective': self.ampl.obj['Total_Cost'].value(),
            'x_values': self.ampl.var['x'].getValues().toDict(),
            'y_values': self.ampl.var['y'].getValues().toDict()
        }

    def solve_with_gomory(self, max_iterations=100):
        """Implementa i Gomory cuts"""
        iteration = 0

        while iteration < max_iterations:
            # Risolvi il problema corrente
            result = self.solve_linear_relaxation()

            # Controlla se la soluzione è intera
            if self.is_integer_solution(result):
                return result

            # Aggiungi Gomory cut
            self.add_gomory_cut(result)
            iteration += 1

        return result

    def is_integer_solution(self, solution, tolerance=1e-6):
        """Verifica se la soluzione è intera"""
        for value in solution['x_values'].values():
            if abs(value - round(value)) > tolerance:
                return False
        return True

    def add_gomory_cut(self, solution):
        """Aggiunge un taglio di Gomory"""
        # Trova la variabile più frazionaria
        max_frac = 0
        cut_var = None

        for var, value in solution['x_values'].items():
            frac = min(value - int(value), int(value) + 1 - value)
            if frac > max_frac:
                max_frac = frac
                cut_var = var

        if cut_var:
            # Aggiungi il taglio (implementazione semplificata)
            cut_name = f"gomory_cut_{len(self.ampl.getConstraints())}"
            # Qui dovresti implementare la logica completa del taglio di Gomory
            pass