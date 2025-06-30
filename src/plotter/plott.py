from os import makedirs
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.use('Qt5Agg')  # Fixed typo: was 'maptlotlib'
from analysis.gomory_cut import *


def plot_gomory_efficiency(results: List):
    """
    Genera un grafico che mostra l'andamento del valore obiettivo e del gap
    rispetto all'ottimo intero durante le iterazioni dei tagli di Gomory.
    """
    if not results:
        print("Nessun risultato da visualizzare")
        return

    # Estrai i dati dai risultati
    file_names = [res['file'] for res in results]
    obj_values = [res['total_cost'] for res in results]
    iterations = [res['iterations'] for res in results]
    cuts_added = [res['cuts_added'] for res in results]

    # Trova il valore obiettivo migliore (minimo)
    best_obj = min(obj_values)

    plt.figure(figsize=(15, 10))

    # Plot 1: Valore obiettivo per istanza
    plt.subplot(2, 2, 1)
    bars = plt.bar(range(len(file_names)), obj_values, alpha=0.7, color='skyblue')
    plt.axhline(y=best_obj, color='r', linestyle='--', label=f'Miglior soluzione: {best_obj:.2f}')
    plt.xlabel("Istanze")
    plt.ylabel("Valore obiettivo")
    plt.title("Valore obiettivo per istanza")
    plt.xticks(range(len(file_names)), [f.replace('.txt', '') for f in file_names], rotation=45)
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Aggiungi etichette sui bar
    for i, (bar, val) in enumerate(zip(bars, obj_values)):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(obj_values) * 0.01,
                 f'{val:.1f}', ha='center', va='bottom', fontsize=8)

    # Plot 2: Numero di iterazioni per istanza
    plt.subplot(2, 2, 2)
    bars = plt.bar(range(len(file_names)), iterations, alpha=0.7, color='lightgreen')
    plt.xlabel("Istanze")
    plt.ylabel("Numero di iterazioni")
    plt.title("Iterazioni dei tagli di Gomory")
    plt.xticks(range(len(file_names)), [f.replace('.txt', '') for f in file_names], rotation=45)
    plt.grid(True, alpha=0.3)

    # Aggiungi etichette sui bar
    for i, (bar, val) in enumerate(zip(bars, iterations)):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(iterations) * 0.01,
                 f'{val}', ha='center', va='bottom', fontsize=8)

    # Plot 3: Numero di tagli aggiunti per istanza
    plt.subplot(2, 2, 3)
    bars = plt.bar(range(len(file_names)), cuts_added, alpha=0.7, color='orange')
    plt.xlabel("Istanze")
    plt.ylabel("Tagli aggiunti")
    plt.title("Tagli di Gomory aggiunti")
    plt.xticks(range(len(file_names)), [f.replace('.txt', '') for f in file_names], rotation=45)
    plt.grid(True, alpha=0.3)

    # Aggiungi etichette sui bar
    for i, (bar, val) in enumerate(zip(bars, cuts_added)):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(cuts_added) * 0.01,
                 f'{val}', ha='center', va='bottom', fontsize=8)

    # Plot 4: Scatter plot iterazioni vs valore obiettivo
    plt.subplot(2, 2, 4)
    plt.scatter(iterations, obj_values, alpha=0.7, s=100, c='purple')
    for i, txt in enumerate([f.replace('.txt', '') for f in file_names]):
        plt.annotate(txt, (iterations[i], obj_values[i]), xytext=(5, 5),
                     textcoords='offset points', fontsize=8)
    plt.xlabel("Numero di iterazioni")
    plt.ylabel("Valore obiettivo")
    plt.title("Correlazione iterazioni-obiettivo")
    plt.grid(True, alpha=0.3)

    plt.tight_layout()

    # Salva il grafico in una cartella 'plots'
    makedirs('results', exist_ok=True)
    plt.savefig('results/gomory_efficiency.png', dpi=300, bbox_inches='tight')
    plt.show()


def plot_individual_convergence(result_with_history):
    """
    Plotta la convergenza per una singola istanza mostrando l'evoluzione
    del valore obiettivo attraverso le iterazioni dei tagli di Gomory.
    """
    if 'cuts_history' not in result_with_history or not result_with_history['cuts_history']:
        print("Nessuna storia dei tagli disponibile per il plot di convergenza")
        return

    history = result_with_history['cuts_history']
    iterations = list(range(len(history)))
    obj_values = [step['objective_value'] for step in history]

    plt.figure(figsize=(10, 6))
    plt.plot(iterations, obj_values, marker='o', linewidth=2, markersize=6)
    plt.xlabel("Iterazione")
    plt.ylabel("Valore obiettivo")
    plt.title(f"Convergenza dei tagli di Gomory - {result_with_history.get('file', 'Istanza')}")
    plt.grid(True, alpha=0.3)

    # Evidenzia il valore finale
    if obj_values:
        plt.axhline(y=obj_values[-1], color='r', linestyle='--', alpha=0.7,
                    label=f'Valore finale: {obj_values[-1]:.2f}')
        plt.legend()

    plt.tight_layout()
    makedirs('results', exist_ok=True)
    plt.savefig(f'results/convergence_{result_with_history.get("file", "instance").replace(".txt", "")}.png',
                dpi=300, bbox_inches='tight')
    plt.show()


def print_summary_table(results: List):
    
    #Stampa una tabella riassuntiva dei risultati di tutte le istanze.
   
    if not results:
        print("Nessun risultato da mostrare")
        return

    print("\n" + "=" * 80)
    print("RIASSUNTO RISULTATI TUTTE LE ISTANZE")
    print("=" * 80)

    # Header della tabella
    header = f"{'Istanza':<15} {'Obj. Value':<12} {'Iterazioni':<12} {'Tagli':<8} {'Status':<10}"
    print(header)
    print("-" * len(header))

    # Dati delle istanze
    total_iterations = 0
    total_cuts = 0
    best_obj = float('inf')
    best_file = ""

    for result in results:
        file_name = result['file'].replace('.txt', '')
        obj_val = result['total_cost']
        iterations = result['iterations']
        cuts = result['cuts_added']

        total_iterations += iterations
        total_cuts += cuts

        if obj_val < best_obj:
            best_obj = obj_val
            best_file = file_name

        print(f"{file_name:<15} {obj_val:<12.2f} {iterations:<12} {cuts:<8} {'OK':<10}")

    print("-" * len(header))
    print(f"{'TOTALI':<15} {'':<12} {total_iterations:<12} {total_cuts:<8}")
    print(f"{'MEDIA':<15} {'':<12} {total_iterations / len(results):<12.1f} {total_cuts / len(results):<8.1f}")
    print(f"\nMIGLIOR SOLUZIONE: {best_file} con valore obiettivo {best_obj:.2f}")
    print("=" * 80)
