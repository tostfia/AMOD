from os import makedirs
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from typing import List, Dict, Any

matplotlib.use('Qt5Agg')

def plot_gomory_efficiency(results: List[Dict[str, Any]]):
    """
    Genera un grafico che mostra l'efficienza dei tagli di Gomory
    analizzando convergenza, gap reduction e performance generale.
    """
    if not results:
        print("Nessun risultato da visualizzare")
        return

    # Estrai i dati dai risultati
    file_names = [res.get('filename', res.get('file', f'Instance_{i}')) for i, res in enumerate(results)]
    obj_values = [res.get('optimal_value', res.get('total_cost', 0)) for res in results]
    iterations = [res.get('iterations', 0) for res in results]
    cuts_added = [res.get('cuts_added', 0) for res in results]

    # Calcola metriche di efficienza
    efficiency_metrics = []
    for res in results:
        obj_history = res.get('objective_history', [])
        if len(obj_history) > 1:
            # Calcola il miglioramento per iterazione
            initial_obj = obj_history[0]
            final_obj = obj_history[-1]
            total_improvement = abs(initial_obj - final_obj) if initial_obj != 0 else 0
            avg_improvement_per_iter = total_improvement / len(obj_history) if len(obj_history) > 0 else 0

            # Efficienza = miglioramento / (iterazioni + tagli)
            efficiency = total_improvement / (res.get('iterations', 1) + res.get('cuts_added', 0)) if (res.get('iterations', 1) + res.get('cuts_added', 0)) > 0 else 0
        else:
            avg_improvement_per_iter = 0
            efficiency = 0

        efficiency_metrics.append({
            'avg_improvement_per_iter': avg_improvement_per_iter,
            'efficiency': efficiency
        })

    plt.figure(figsize=(16, 12))

    # Plot 1: Valore obiettivo per istanza
    plt.subplot(2, 3, 1)
    bars = plt.bar(range(len(file_names)), obj_values, alpha=0.7, color='skyblue')
    if obj_values:
        best_obj = min(obj_values)
        plt.axhline(y=best_obj, color='r', linestyle='--', label=f'Miglior soluzione: {best_obj:.2f}')
    plt.xlabel("Istanze")
    plt.ylabel("Valore obiettivo")
    plt.title("Valore obiettivo per istanza")
    plt.xticks(range(len(file_names)), [f.replace('.txt', '') for f in file_names], rotation=45)
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Aggiungi etichette sui bar
    for i, (bar, val) in enumerate(zip(bars, obj_values)):
        if val > 0:
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(obj_values) * 0.01,
                     f'{val:.1f}', ha='center', va='bottom', fontsize=8)

    # Plot 2: Efficienza dei tagli (miglioramento per iterazione)
    plt.subplot(2, 3, 2)
    efficiency_vals = [m['avg_improvement_per_iter'] for m in efficiency_metrics]
    bars = plt.bar(range(len(file_names)), efficiency_vals, alpha=0.7, color='lightgreen')
    plt.xlabel("Istanze")
    plt.ylabel("Miglioramento medio per iterazione")
    plt.title("Efficienza dei Tagli di Gomory")
    plt.xticks(range(len(file_names)), [f.replace('.txt', '') for f in file_names], rotation=45)
    plt.grid(True, alpha=0.3)

    # Aggiungi etichette sui bar
    for i, (bar, val) in enumerate(zip(bars, efficiency_vals)):
        if val > 0:
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(efficiency_vals) * 0.01,
                     f'{val:.3f}', ha='center', va='bottom', fontsize=8)

    # Plot 3: Numero di iterazioni vs tagli aggiunti
    plt.subplot(2, 3, 3)
    plt.scatter(iterations, cuts_added, alpha=0.7, s=100, c='orange')
    for i, txt in enumerate([f.replace('.txt', '') for f in file_names]):
        plt.annotate(txt, (iterations[i], cuts_added[i]), xytext=(5, 5),
                     textcoords='offset points', fontsize=8)
    plt.xlabel("Numero di iterazioni")
    plt.ylabel("Tagli aggiunti")
    plt.title("Iterazioni vs Tagli Aggiunti")
    plt.grid(True, alpha=0.3)

    # Plot 4: Ratio efficienza (tagli utili vs totali)
    plt.subplot(2, 3, 4)
    # Calcola il ratio di efficienza (assumiamo che tagli utili = iterazioni effettive)
    cut_efficiency = []
    for i in range(len(results)):
        if cuts_added[i] > 0 and iterations[i] > 0:
            # Ratio: iterazioni necessarie / tagli totali (più basso = più efficiente)
            ratio = iterations[i] / cuts_added[i]
        else:
            ratio = 0
        cut_efficiency.append(ratio)

    bars = plt.bar(range(len(file_names)), cut_efficiency, alpha=0.7, color='purple')
    plt.xlabel("Istanze")
    plt.ylabel("Ratio Iterazioni/Tagli")
    plt.title("Efficienza dei Tagli (ratio più basso = migliore)")
    plt.xticks(range(len(file_names)), [f.replace('.txt', '') for f in file_names], rotation=45)
    plt.grid(True, alpha=0.3)

    # Plot 5: Scatter plot efficienza generale
    plt.subplot(2, 3, 5)
    overall_efficiency = [m['efficiency'] for m in efficiency_metrics]
    plt.scatter(iterations, overall_efficiency, alpha=0.7, s=100, c='red')
    for i, txt in enumerate([f.replace('.txt', '') for f in file_names]):
        plt.annotate(txt, (iterations[i], overall_efficiency[i]), xytext=(5, 5),
                     textcoords='offset points', fontsize=8)
    plt.xlabel("Numero di iterazioni")
    plt.ylabel("Efficienza complessiva")
    plt.title("Correlazione Iterazioni-Efficienza")
    plt.grid(True, alpha=0.3)

    # Plot 6: Box plot delle performance
    plt.subplot(2, 3, 6)
    data_for_boxplot = [iterations, cuts_added, efficiency_vals]
    labels = ['Iterazioni', 'Tagli', 'Efficienza']

    # Normalizza i dati per il confronto
    normalized_data = []
    for data in data_for_boxplot:
        if data and max(data) > 0:
            normalized = [x / max(data) for x in data]
        else:
            normalized = data
        normalized_data.append(normalized)

    plt.boxplot(normalized_data, labels=labels)
    plt.ylabel("Valori normalizzati")
    plt.title("Distribuzione delle Performance")
    plt.grid(True, alpha=0.3)

    plt.tight_layout()

    # Salva il grafico in una cartella 'results'
    makedirs('results', exist_ok=True)
    plt.savefig('results/gomory_efficiency.png', dpi=300, bbox_inches='tight')
    plt.show()


def plot_individual_convergence(result_with_history):
    """
    Plotta la convergenza per una singola istanza mostrando l'evoluzione
    del valore obiettivo attraverso le iterazioni dei tagli di Gomory.
    """
    # Gestisci diversi formati di input
    filename = result_with_history.get('filename', result_with_history.get('file', 'Istanza'))
    obj_history = result_with_history.get('objective_history',
                                          result_with_history.get('cuts_history', []))

    if not obj_history:
        print(f"Nessuna storia dei tagli disponibile per {filename}")
        return

    # Se obj_history contiene dizionari, estrai i valori obiettivo
    if obj_history and isinstance(obj_history[0], dict):
        obj_values = [step.get('objective_value', 0) for step in obj_history]
    else:
        obj_values = obj_history

    iterations = list(range(len(obj_values)))

    plt.figure(figsize=(12, 8))

    # Plot principale della convergenza
    plt.subplot(2, 1, 1)
    plt.plot(iterations, obj_values, marker='o', linewidth=2, markersize=6, color='blue')
    plt.xlabel("Iterazione")
    plt.ylabel("Valore obiettivo")
    plt.title(f"Convergenza dei tagli di Gomory - {filename.replace('.txt', '')}")
    plt.grid(True, alpha=0.3)

    # Evidenzia il valore finale
    if obj_values:
        plt.axhline(y=obj_values[-1], color='r', linestyle='--', alpha=0.7,
                    label=f'Valore finale: {obj_values[-1]:.2f}')
        plt.legend()

    # Plot del miglioramento per iterazione
    plt.subplot(2, 1, 2)
    if len(obj_values) > 1:
        improvements = []
        for i in range(1, len(obj_values)):
            improvement = abs(obj_values[i-1] - obj_values[i])
            improvements.append(improvement)

        plt.bar(range(1, len(obj_values)), improvements, alpha=0.7, color='green')
        plt.xlabel("Iterazione")
        plt.ylabel("Miglioramento")
        plt.title("Miglioramento per Iterazione")
        plt.grid(True, alpha=0.3)

        # Aggiungi linea di tendenza
        if len(improvements) > 1:
            z = np.polyfit(range(len(improvements)), improvements, 1)
            p = np.poly1d(z)
            plt.plot(range(1, len(obj_values)), p(range(len(improvements))),
                     "r--", alpha=0.8, label='Tendenza')
            plt.legend()

    plt.tight_layout()
    makedirs('results', exist_ok=True)
    safe_filename = filename.replace('.txt', '').replace('/', '_').replace('\\', '_')
    plt.savefig(f'results/convergence_{safe_filename}.png', dpi=300, bbox_inches='tight')
    plt.show()


def plot_efficiency_comparison(results: List[Dict[str, Any]]):
    """
    Crea un grafico comparativo dell'efficienza dei tagli di Gomory
    mostrando diverse metriche di performance.
    """
    if not results:
        print("Nessun risultato da visualizzare")
        return

    # Prepara i dati
    file_names = [res.get('filename', res.get('file', f'Instance_{i}'))
                  for i, res in enumerate(results)]

    # Calcola metriche di efficienza avanzate
    metrics = []
    for res in results:
        obj_history = res.get('objective_history', [])
        iterations = res.get('iterations', 0)
        cuts_added = res.get('cuts_added', 0)

        if len(obj_history) > 1:
            # Velocità di convergenza
            initial_obj = obj_history[0]
            final_obj = obj_history[-1]
            convergence_rate = abs(final_obj - initial_obj) / len(obj_history) if len(obj_history) > 0 else 0

            # Efficienza dei tagli (miglioramento per taglio)
            cut_efficiency = abs(final_obj - initial_obj) / cuts_added if cuts_added > 0 else 0

            # Stabilità (varianza delle differenze consecutive)
            if len(obj_history) > 2:
                diffs = [abs(obj_history[i] - obj_history[i-1]) for i in range(1, len(obj_history))]
                stability = 1 / (np.var(diffs) + 1e-6)  # Inverso della varianza
            else:
                stability = 1

        else:
            convergence_rate = 0
            cut_efficiency = 0
            stability = 0

        metrics.append({
            'convergence_rate': convergence_rate,
            'cut_efficiency': cut_efficiency,
            'stability': stability,
            'iterations': iterations,
            'cuts_added': cuts_added
        })

    # Crea il grafico
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # 1. Velocità di convergenza
    convergence_rates = [m['convergence_rate'] for m in metrics]
    axes[0, 0].bar(range(len(file_names)), convergence_rates, alpha=0.7, color='skyblue')
    axes[0, 0].set_title('Velocità di Convergenza')
    axes[0, 0].set_xlabel('Istanze')
    axes[0, 0].set_ylabel('Miglioramento medio per iterazione')
    axes[0, 0].tick_params(axis='x', rotation=45)
    axes[0, 0].grid(True, alpha=0.3)

    # 2. Efficienza dei tagli
    cut_efficiencies = [m['cut_efficiency'] for m in metrics]
    axes[0, 1].bar(range(len(file_names)), cut_efficiencies, alpha=0.7, color='lightgreen')
    axes[0, 1].set_title('Efficienza dei Tagli')
    axes[0, 1].set_xlabel('Istanze')
    axes[0, 1].set_ylabel('Miglioramento per taglio')
    axes[0, 1].tick_params(axis='x', rotation=45)
    axes[0, 1].grid(True, alpha=0.3)

    # 3. Stabilità della convergenza
    stabilities = [m['stability'] for m in metrics]
    axes[1, 0].bar(range(len(file_names)), stabilities, alpha=0.7, color='orange')
    axes[1, 0].set_title('Stabilità della Convergenza')
    axes[1, 0].set_xlabel('Istanze')
    axes[1, 0].set_ylabel('Indice di stabilità')
    axes[1, 0].tick_params(axis='x', rotation=45)
    axes[1, 0].grid(True, alpha=0.3)

    # 4. Scatter plot efficienza complessiva
    overall_efficiency = [c * s for c, s in zip(convergence_rates, stabilities)]
    iterations_list = [m['iterations'] for m in metrics]

    scatter = axes[1, 1].scatter(iterations_list, overall_efficiency,
                                 alpha=0.7, s=100, c=cut_efficiencies, cmap='viridis')
    axes[1, 1].set_title('Efficienza Complessiva vs Iterazioni')
    axes[1, 1].set_xlabel('Numero di iterazioni')
    axes[1, 1].set_ylabel('Efficienza complessiva')
    axes[1, 1].grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=axes[1, 1], label='Efficienza tagli')

    # Aggiungi etichette alle istanze nei scatter plots
    for i, name in enumerate(file_names):
        short_name = name.replace('.txt', '')[:8]  # Tronca per leggibilità
        axes[1, 1].annotate(short_name, (iterations_list[i], overall_efficiency[i]),
                            xytext=(5, 5), textcoords='offset points', fontsize=8)

    plt.tight_layout()
    makedirs('results', exist_ok=True)
    plt.savefig('results/gomory_efficiency_comparison.png', dpi=300, bbox_inches='tight')
    plt.show()


def print_summary_table(results: List[Dict[str, Any]]):
    """
    Stampa una tabella riassuntiva dei risultati di tutte le istanze
    con metriche di efficienza.
    """
    if not results:
        print("Nessun risultato da mostrare")
        return

    print("\n" + "=" * 100)
    print("RIASSUNTO RISULTATI E ANALISI EFFICIENZA TAGLI DI GOMORY")
    print("=" * 100)

    # Header della tabella esteso
    header = f"{'Istanza':<15} {'Obj. Value':<12} {'Iterazioni':<12} {'Tagli':<8} {'Efficienza':<12} {'Status':<10}"
    print(header)
    print("-" * len(header))

    # Calcola statistiche
    total_iterations = 0
    total_cuts = 0
    total_efficiency = 0
    best_obj = float('inf')
    best_file = ""
    most_efficient = {"file": "", "efficiency": 0}

    for result in results:
        filename = result.get('filename', result.get('file', 'Unknown'))
        file_name = filename.replace('.txt', '')
        obj_val = result.get('optimal_value', result.get('total_cost', 0))
        iterations = result.get('iterations', 0)
        cuts = result.get('cuts_added', 0)

        # Calcola efficienza
        obj_history = result.get('objective_history', [])
        if len(obj_history) > 1 and cuts > 0:
            improvement = abs(obj_history[0] - obj_history[-1])
            efficiency = improvement / cuts
        else:
            efficiency = 0

        total_iterations += iterations
        total_cuts += cuts
        total_efficiency += efficiency

        if obj_val > 0 and obj_val < best_obj:
            best_obj = obj_val
            best_file = file_name

        if efficiency > most_efficient["efficiency"]:
            most_efficient = {"file": file_name, "efficiency": efficiency}

        print(f"{file_name:<15} {obj_val:<12.2f} {iterations:<12} {cuts:<8} {efficiency:<12.3f} {'OK':<10}")

    num_results = len(results)
    print("-" * len(header))
    print(f"{'TOTALI':<15} {'':<12} {total_iterations:<12} {total_cuts:<8} {total_efficiency:<12.3f}")
    print(f"{'MEDIA':<15} {'':<12} {total_iterations/num_results:<12.1f} {total_cuts/num_results:<8.1f} {total_efficiency/num_results:<12.3f}")

    print(f"\n🏆 MIGLIORE SOLUZIONE: {best_file} con valore obiettivo {best_obj:.2f}")
    print(f"⚡ PIÙ EFFICIENTE: {most_efficient['file']} con efficienza {most_efficient['efficiency']:.3f}")

    # Analisi dell'efficienza
    efficiencies = []
    for result in results:
        obj_history = result.get('objective_history', [])
        cuts = result.get('cuts_added', 0)
        if len(obj_history) > 1 and cuts > 0:
            improvement = abs(obj_history[0] - obj_history[-1])
            efficiency = improvement / cuts
            efficiencies.append(efficiency)

    if efficiencies:
        avg_efficiency = np.mean(efficiencies)
        std_efficiency = np.std(efficiencies)
        print(f"📊 EFFICIENZA MEDIA: {avg_efficiency:.3f} ± {std_efficiency:.3f}")
        print(f"📈 RANGE EFFICIENZA: {min(efficiencies):.3f} - {max(efficiencies):.3f}")

    print("=" * 100)


def print_efficiency_analysis(results: List[Dict[str, Any]]):
    """
    Stampa un'analisi dettagliata dell'efficienza dei tagli di Gomory.
    """
    if not results:
        return

    print("\n" + "🔍 ANALISI DETTAGLIATA EFFICIENZA TAGLI DI GOMORY")
    print("=" * 80)

    # Raccogli metriche
    convergence_data = []
    for result in results:
        obj_history = result.get('objective_history', [])
        if len(obj_history) > 1:
            # Analizza la convergenza
            improvements = []
            for i in range(1, len(obj_history)):
                imp = abs(obj_history[i-1] - obj_history[i])
                improvements.append(imp)

            # Trova quando la convergenza rallenta
            if len(improvements) > 3:
                early_avg = np.mean(improvements[:len(improvements)//2])
                late_avg = np.mean(improvements[len(improvements)//2:])
                slowdown_factor = early_avg / late_avg if late_avg > 0 else float('inf')
            else:
                slowdown_factor = 1

            convergence_data.append({
                'filename': result.get('filename', 'Unknown'),
                'total_improvement': sum(improvements),
                'avg_improvement': np.mean(improvements),
                'early_power': early_avg,
                'late_power': late_avg,
                'slowdown_factor': slowdown_factor,
                'iterations': result.get('iterations', 0),
                'cuts': result.get('cuts_added', 0)
            })

    if convergence_data:
        print(f"📊 Istanze analizzate: {len(convergence_data)}")

        # Trova patterns
        high_efficiency = [d for d in convergence_data if d['avg_improvement'] > np.mean([d['avg_improvement'] for d in convergence_data])]
        low_slowdown = [d for d in convergence_data if d['slowdown_factor'] < 2.0]

        print(f"⚡ Istanze ad alta efficienza: {len(high_efficiency)}")
        print(f"🎯 Istanze con convergenza stabile: {len(low_slowdown)}")

        if high_efficiency:
            print(f"\n🏆 ISTANZE PIÙ EFFICIENTI:")
            for data in sorted(high_efficiency, key=lambda x: x['avg_improvement'], reverse=True)[:3]:
                print(f"   • {data['filename'].replace('.txt', '')}: "
                      f"miglioramento medio {data['avg_improvement']:.3f}")

        print("=" * 80)