//
//  PainelWidgetBundle.swift
//  PainelWidget (WidgetKit extension)
//
//  Ponto de entrada `@main` da extensão. O construtor do WidgetBundle aceita até 10 widgets por bloco, então
//  os da tela de início (leva de 2026-11-05) ficam num segundo pacote aninhado pelo `.body`.
//
//  Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import WidgetKit
import SwiftUI

@main
struct PainelWidgetBundle: WidgetBundle {
    var body: some Widget {
        PainelWidget()  // Próximo: quanto falta pra sair (PainelWidget.swift)
        ProximoCompromisso()  // tela bloqueada: próximo compromisso de saída/voo (ProximoCompromisso.swift)
        AtividadeCompromisso()  // atividade ao vivo + Dynamic Island do compromisso (AtividadeCompromisso.swift)
        IlhaTeste()  // atividade de teste da tela "Gerar relatório" do app (IlhaTeste.swift)
        WidgetsDaTelaDeInicio().body
        #if compiler(>=6.0)
        if #available(iOS 18.0, *) {
            PainelControle()  // Central de Controle: botão "Anotar no painel" (PainelControle.swift)
        }
        #endif
    }
}

/// Os widgets da tela de início votados no protótipo (docs/briefings/2026-11-05-widgets-ios.md).
struct WidgetsDaTelaDeInicio: WidgetBundle {
    var body: some Widget {
        PainelProteina()  // WidgetsCorpo.swift
        PainelAgua()
        PainelDia()  // WidgetsDia.swift
        PainelHoje()
        PainelConta()
        PainelVoo()  // WidgetsVoo.swift
        PainelHoras()
    }
}
