import sys
import logging
from pathlib import Path

from config import *
from plotter.plott import *
from utility.facilityLocation import FacilityLocationModel
from utility.utils import *
from analysis.gomory_cut import *


def setup_logging():
    """Configura il logging per l'applicazione"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('ufl_solver.log'),
            logging.StreamHandler()
        ]
    )


def print_menu():
    """Stampa il menu delle opzioni"""
    print("\n" + "=" * 60)
    print("           UFL SOLVER CON TAGLI DI GOMORY")
    print("=" * 60)
    print("1. Risolvi tutte le istanze")
    print("2. Genera istanza casuale")
    print("3. Risolvi singola istanza")
    print("4. Esci")
    print("=" * 60)


def print_result_details(result: dict, filename: str):
    """Stampa i dettagli di un risultato in modo formattato"""
    print(f"\n📁 File: {filename}")
    print("-" * 50)

    if result['success']:
        print(f"✅ SUCCESSO")
        print(f"🎯 Valore ottimo: {result['optimal_value']:.6f}")
        print(f"🔢 Costo intero: {'Sì' if result['is_integer_cost'] else 'No'}")
        print(f"🏭 Facilities aperte: {len(result['open_facilities'])}")
        print(f"📍 Indici facilities: {result['open_facilities']}")
        print(f"🔄 Iterazioni: {result['iterations']}")
        print(f"✂️  Tagli aggiunti: {result['cuts_added']}")

        # Mostra alcune allocazioni come esempio
        allocations = result['allocations']
        if allocations:
            print(f"🔗 Allocazioni (primi 5): {dict(list(allocations.items())[:5])}")
            if len(allocations) > 5:
                print(f"    ... e altre {len(allocations) - 5} allocazioni")
    else:
        print(f"❌ FALLIMENTO")
        print(f"💬 Messaggio: {result.get('message', 'Errore sconosciuto')}")
        if 'last_objective' in result and result['last_objective']:
            print(f"🎯 Ultimo valore: {result['last_objective']:.6f}")
        print(f"🔄 Iterazioni: {result.get('iterations', 0)}")
        print(f"✂️  Tagli aggiunti: {result.get('cuts_added', 0)}")


def process_single_instance(filepath: Path) -> dict:
    """
    Elabora una singola istanza e restituisce i risultati

    Args:
        filepath: Percorso del file dell'istanza

    Returns:
        Dizionario con i risultati dell'elaborazione
    """
    try:
        print(f"\n🔄 Elaborazione: {filepath.name}")

        # Carica il modello
        model = FacilityLocationModel.from_file(filepath)
        print(f"📊 Modello caricato: {model.get_num_facilities()} facilities, "
              f"{model.get_num_customers()} clienti")

        # Risolvi con Gomory cuts
        gc = gomoryCut(model)
        result = gc.solve_with_gomory_cuts(MAX_ITERATIONS)

        # Aggiungi informazioni sul file
        result['filename'] = filepath.name
        result['filepath'] = str(filepath)

        return result

    except Exception as e:
        logging.error(f"Errore durante l'elaborazione di {filepath}: {e}")
        return {
            'success': False,
            'error': True,
            'message': str(e),
            'filename': filepath.name,
            'filepath': str(filepath)
        }


def process_all_instances():
    """Gestisce l'opzione per risolvere tutte le istanze."""
    print("\n🚀 Avvio risoluzione di tutte le istanze...")

    directory = DATA_DIR
    if not directory.exists():
        print(f"❌ Errore: directory {directory} non trovata")
        return

    # Trova tutti i file .txt
    txt_files = list(directory.rglob('*.txt'))
    if not txt_files:
        print(f"⚠️  Nessun file .txt trovato in {directory}")
        return

    print(f"📂 Trovati {len(txt_files)} file da elaborare")

    # Lista per memorizzare tutti i risultati
    results = []
    successful_instances = 0
    failed_instances = 0

    # Elabora ogni istanza
    for i, file_path in enumerate(txt_files, 1):
        print(f"\n[{i}/{len(txt_files)}] " + "="*40)

        result = process_single_instance(file_path)
        results.append(result)

        # Mostra risultato immediato
        print_result_details(result, file_path.name)

        if result['success']:
            successful_instances += 1
        else:
            failed_instances += 1

    # Stampa riepilogo finale
    print("\n" + "="*60)
    print("📈 RIEPILOGO FINALE")
    print("="*60)
    print(f"✅ Istanze risolte con successo: {successful_instances}")
    print(f"❌ Istanze fallite: {failed_instances}")
    print(f"📊 Totale istanze: {len(txt_files)}")
    print(f"📈 Tasso di successo: {(successful_instances/len(txt_files)*100):.1f}%")

    # Statistiche dettagliate per le istanze di successo
    if successful_instances > 0:
        successful_results = [r for r in results if r['success']]

        total_iterations = sum(r['iterations'] for r in successful_results)
        total_cuts = sum(r['cuts_added'] for r in successful_results)
        avg_iterations = total_iterations / successful_instances
        avg_cuts = total_cuts / successful_instances

        print(f"🔄 Media iterazioni: {avg_iterations:.1f}")
        print(f"✂️  Media tagli: {avg_cuts:.1f}")

        # Trova miglior e peggior performance
        best_result = min(successful_results, key=lambda x: x['iterations'])
        worst_result = max(successful_results, key=lambda x: x['iterations'])

        print(f"🏆 Miglior performance: {best_result['filename']} ({best_result['iterations']} iter)")
        print(f"🐌 Peggior performance: {worst_result['filename']} ({worst_result['iterations']} iter)")

    # Genera grafici se disponibili
    try:
        if successful_instances > 0:
            print(f"\n📊 Generazione grafici...")
            # Adatta i risultati per i grafici esistenti
            plot_data = []
            for result in results:
                if result['success']:
                    plot_data.append({
                        "file": result['filename'],
                        "total_cost": result['optimal_value'],
                        "iterations": result['iterations'],
                        "cuts_added": result['cuts_added'],
                        "objective_history": result.get('objective_history', [])
                    })

            if plot_data:
                print_summary_table(plot_data)
                plot_gomory_efficiency(plot_data)

                # Genera grafici individuali per le prime istanze
                for idx, data in enumerate(plot_data[:5]):  # Limita a 5 per non sovraccaricare
                    plot_individual_convergence(data)

                print("📈 Grafici generati con successo!")

    except Exception as e:
        print(f"⚠️  Errore nella generazione dei grafici: {e}")

    # Salva risultati in un file JSON per analisi future
    try:
        import json
        results_file = Path("results_gomory.json")
        with open(results_file, 'w') as f:
            # Converti Path objects in stringhe per JSON
            json_results = []
            for r in results:
                json_r = r.copy()
                if 'filepath' in json_r:
                    json_r['filepath'] = str(json_r['filepath'])
                json_results.append(json_r)

            json.dump(json_results, f, indent=2)
        print(f"💾 Risultati salvati in: {results_file}")
    except Exception as e:
        print(f"⚠️  Errore nel salvataggio: {e}")


def process_single_instance_interactive():
    """Permette di risolvere una singola istanza scelta dall'utente"""
    directory = DATA_DIR
    if not directory.exists():
        print(f"❌ Errore: directory {directory} non trovata")
        return

    # Trova tutti i file .txt
    txt_files = list(directory.rglob('*.txt'))
    if not txt_files:
        print(f"⚠️  Nessun file .txt trovato in {directory}")
        return

    # Mostra lista file
    print(f"\n📂 File disponibili:")
    for i, file_path in enumerate(txt_files, 1):
        print(f"{i:2d}. {file_path.name}")

    try:
        choice = int(input(f"\nScegli un file (1-{len(txt_files)}): "))
        if 1 <= choice <= len(txt_files):
            selected_file = txt_files[choice - 1]
            result = process_single_instance(selected_file)
            print_result_details(result, selected_file.name)
        else:
            print("❌ Scelta non valida")
    except ValueError:
        print("❌ Inserisci un numero valido")


def generate_random_instance():
    """Gestisce la generazione di un'istanza casuale"""
    try:
        user_input = input(
            "Inserisci il numero dell'istanza, facilities e clienti "
            "(es: 1 10 50): "
        ).strip()

        instance_id, num_facilities, num_customers = map(int, user_input.split())

        print(f"🎲 Generazione istanza {instance_id}: "
              f"{num_facilities} facilities, {num_customers} clienti")

        model = generateInstance(instance_id, num_facilities, num_customers)
        print(f"✅ Istanza generata: {model}")

        # Chiedi se risolvere immediatamente
        solve_now = input("Vuoi risolvere questa istanza ora? (s/n): ").strip().lower()
        if solve_now in ['s', 'si', 'y', 'yes']:
            print("\n🔄 Risoluzione istanza generata...")
            # Risolvi con Gomory cuts
            gc = gomoryCut(model)
            result = gc.solve_with_gomory_cuts(MAX_ITERATIONS)
            print_result_details(result, f"Random_Instance_{instance_id}")

    except ValueError:
        print("❌ Errore: assicurati di inserire tre numeri separati da spazio.")
    except Exception as e:
        print(f"❌ Errore inaspettato: {e}")


def main():
    """Funzione principale con menu interattivo."""
    setup_logging()

    print("🚀 Avvio UFL Solver con Tagli di Gomory")

    while True:
        print_menu()

        try:
            choice = input("Scegli un'opzione (1-4): ").strip()

            if choice == '1':
                process_all_instances()

            elif choice == '2':
                generate_random_instance()

            elif choice == '3':
                process_single_instance_interactive()

            elif choice == '4':
                print("👋 Uscita dal programma. Arrivederci!")
                sys.exit(0)

            else:
                print("❌ Opzione non valida. Scegli 1, 2, 3 o 4.")

        except KeyboardInterrupt:
            print("\n\n👋 Interruzione da tastiera. Arrivederci!")
            sys.exit(0)
        except Exception as e:
            logging.error(f"Errore inaspettato nel main: {e}")
            print(f"❌ Errore inaspettato: {e}")

        # Pausa prima di mostrare di nuovo il menu
        input("\n⏸️  Premi Invio per continuare...")


if __name__ == "__main__":
    main()