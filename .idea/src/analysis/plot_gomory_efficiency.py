import matplotlib.pyplot as plt

def plot_gomory_efficiency(results, z_optimal):
    iterations = list(range(1, len(results['obj_values']) + 1))
    obj_values = results['obj_values']
    cuts = results['cuts']
    gaps = [(obj - z_optimal) for obj in obj_values]

    plt.figure(figsize=(12, 6))

    # Plot valore obiettivo
    plt.subplot(1, 2, 1)
    plt.plot(iterations, obj_values, marker='o', label='Valore obiettivo')
    plt.axhline(y=z_optimal, color='r', linestyle='--', label='Ottimo intero')
    plt.xlabel("Iterazione")
    plt.ylabel("Valore obiettivo")
    plt.title("Convergenza dei tagli di Gomory")
    plt.legend()

    # Plot gap
    plt.subplot(1, 2, 2)
    plt.plot(iterations, gaps, marker='x', color='orange', label='Gap rispetto all’ottimo')
    plt.xlabel("Iterazione")
    plt.ylabel("Gap")
    plt.title("Gap vs Iterazione")
    plt.legend()

    plt.tight_layout()
    plt.show()
