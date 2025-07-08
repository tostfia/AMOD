from utility.parser import *


class FacilityLocationModel:
    """Modello per problemi di Facility Location (UFL)"""

    def __init__(self, num_facilities, num_customers, fixed_costs, assignment_costs):
        self.num_facilities = num_facilities
        self.num_customers = num_customers
        self.fixed_costs = fixed_costs
        self.assignment_costs = assignment_costs

        # Validazione dei dati
        self._validate_data()

    def _validate_data(self):
        """Valida la consistenza dei dati"""
        if len(self.fixed_costs) != self.num_facilities:
            raise ValueError(f"fixed_costs ha {len(self.fixed_costs)} elementi, "
                             f"ma num_facilities è {self.num_facilities}")

        if len(self.assignment_costs) != self.num_customers:
            raise ValueError(f"assignment_costs ha {len(self.assignment_costs)} righe, "
                             f"ma num_customers è {self.num_customers}")

        for i, row in enumerate(self.assignment_costs):
            if len(row) != self.num_facilities:
                raise ValueError(f"Riga {i} di assignment_costs ha {len(row)} colonne, "
                                 f"attese {self.num_facilities}")

    # Metodi getter (mantenuti per compatibilità)
    def get_num_facilities(self):
        return self.num_facilities

    def get_num_customers(self):
        return self.num_customers

    def get_fixed_costs(self):
        return self.fixed_costs

    def get_assignment_costs(self):
        return self.assignment_costs

    # Metodi aggiuntivi utili
    @classmethod
    def from_dict(cls, data_dict):
        """Crea un'istanza dal dizionario del parser"""
        return cls(
            num_facilities=data_dict['num_facilities'],
            num_customers=data_dict['num_customers'],
            fixed_costs=data_dict['fixed_costs'],
            assignment_costs=data_dict['assignment_costs']
        )

    @classmethod
    def from_file(cls, filename):
        """Crea un'istanza direttamente da file"""
        data = parse_ufl_instance(filename)
        return cls.from_dict(data)

    def __str__(self):
        return (f"UFL Instance: {self.num_facilities} facilities, "
                f"{self.num_customers} customers")

    def __repr__(self):
        return (f"FacilityLocationModel(facilities={self.num_facilities}, "
                f"customers={self.num_customers})")
