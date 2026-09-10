#!/usr/bin/env python3
"""Menu portátil para executar o Jira Sync com argumentos seguros."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable


Runner = Callable[[list[str]], int]


def run_menu(
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], object] = print,
    runner: Runner | None = None,
    allow_simulation: bool = True,
    opener: Callable[[Path], object] | None = None,
    report_dir: Path | None = None,
    now_fn: Callable[[], datetime] = datetime.now,
) -> int:
    script_path = Path(__file__).with_name("jira_sync.py")
    report_dir = report_dir or Path(__file__).with_name("relatorios")
    if runner is None:
        runner = lambda args: subprocess.run(  # noqa: E731 - função curta e local
            [sys.executable, str(script_path), *args], check=False
        ).returncode
    if opener is None:
        opener = lambda path: subprocess.run(["open", str(path)], check=False).returncode  # noqa: E731

    def pause() -> None:
        output_fn("")
        input_fn("Pressione Enter para voltar ao menu...")

    def choose_ai() -> str:
        while True:
            output_fn("")
            output_fn("Usar IA para melhorar as descrições?")
            output_fn("1. Sim")
            output_fn("2. Não")
            choice = input_fn("Escolha: ").strip()
            if choice == "1":
                return "--ai"
            if choice == "2":
                return "--no-ai"
            output_fn("Opção inválida.")

    def read_period() -> list[str]:
        output_fn("")
        start = input_fn("Data inicial (AAAA-MM-DD): ").strip()
        end = input_fn("Data final   (AAAA-MM-DD): ").strip()
        return ["--start", start, "--end", end]

    def report_path(ai_flag: str) -> Path:
        ai_label = "com_ia" if ai_flag == "--ai" else "sem_ia"
        timestamp = now_fn().strftime("%Y%m%d_%H%M%S")
        return report_dir / f"simulacao_jira_sync_{ai_label}_{timestamp}.xlsx"

    def execute(args: list[str], generated_report: Path | None = None) -> None:
        output_fn("")
        result = runner(args)
        if result:
            output_fn("")
            output_fn(f"A execução terminou com erro (código {result}).")
        elif generated_report is not None:
            open_result = opener(generated_report)
            if isinstance(open_result, int) and open_result != 0:
                output_fn(f"Planilha salva em: {generated_report}")
                output_fn("Não foi possível abri-la automaticamente.")
            else:
                output_fn("A planilha foi aberta automaticamente.")
        pause()

    try:
        while True:
            output_fn("")
            output_fn("============================================")
            output_fn("              JIRA SYNC")
            output_fn("============================================")
            output_fn("1. APLICAR - gravar apontamentos no Jira interno")
            if allow_simulation:
                output_fn("2. Simular semana atual e semana anterior com IA")
                output_fn("3. Simular semana atual e semana anterior sem IA")
                output_fn("4. Simular período específico")
                output_fn("5. Simular a semana atual no console")
                output_fn("6. Ajuda do script")
            else:
                output_fn("2. Ajuda do script")
            output_fn("0. Sair")
            output_fn("")
            choice = input_fn("Escolha uma opção: ").strip()

            if choice == "0":
                return 0
            if not allow_simulation and choice == "2":
                execute(["--help"])
                continue
            if allow_simulation and choice == "2":
                report = report_path("--ai")
                execute(["--weeks-back", "2", "--ai", "--output-xlsx", str(report)], report)
                continue
            if allow_simulation and choice == "3":
                report = report_path("--no-ai")
                execute(["--weeks-back", "2", "--no-ai", "--output-xlsx", str(report)], report)
                continue
            if allow_simulation and choice == "4":
                date_args = read_period()
                ai_flag = choose_ai()
                report = report_path(ai_flag)
                execute([*date_args, ai_flag, "--output-xlsx", str(report)], report)
                continue
            if allow_simulation and choice == "5":
                execute(["--weeks-back", "1", choose_ai()])
                continue
            if allow_simulation and choice == "6":
                execute(["--help"])
                continue
            if choice != "1":
                output_fn("Opção inválida.")
                continue

            while True:
                output_fn("")
                output_fn("Período que será aplicado:")
                output_fn("1. Semana atual e semana anterior")
                output_fn("2. Período específico")
                output_fn("0. Voltar")
                period_choice = input_fn("Escolha: ").strip()
                if period_choice == "0":
                    break
                if period_choice == "1":
                    date_args = ["--weeks-back", "2"]
                elif period_choice == "2":
                    date_args = read_period()
                else:
                    output_fn("Opção inválida.")
                    continue

                ai_flag = choose_ai()
                output_fn("")
                output_fn("ATENÇÃO: esta opção gravará apontamentos no Jira interno.")
                output_fn("Registros que fariam o total diário ultrapassar 8h serão bloqueados.")
                confirmation = input_fn(
                    "Pressione Enter para iniciar ou digite CANCELAR: "
                )
                if confirmation:
                    output_fn("Aplicação cancelada.")
                    pause()
                    break
                output_fn("")
                output_fn("🚀 Iniciando processamento. Aguarde...")
                execute([*date_args, ai_flag, "--apply"])
                break
    except (EOFError, KeyboardInterrupt):
        output_fn("")
        return 0


def main() -> int:
    return run_menu(allow_simulation="--windows" not in sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
