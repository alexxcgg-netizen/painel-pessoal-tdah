//
//  PainelWidgetBundle.swift
//  PainelWidget (WidgetKit extension) — Fase 7 / faixa n3e-widgetkit
//
//  Ponto de entrada `@main` da extensão de widget. Só existe um widget por
//  enquanto (`PainelWidget`, em PainelWidget.swift); o bundle já fica pronto
//  pra somar um segundo widget de extensão no futuro (ex: um widget
//  configurável por `AppIntent`) sem precisar mexer no alvo do Xcode.
//
//  IMPORTANTE (ver README.md): não compilado/testado neste ambiente — não
//  há Mac com Xcode aqui.
//

import WidgetKit
import SwiftUI

@main
struct PainelWidgetBundle: WidgetBundle {
    var body: some Widget {
        PainelWidget()
        #if compiler(>=6.0)
        if #available(iOS 18.0, *) {
            PainelControle()  // Central de Controle: botão "Anotar no painel" (PainelControle.swift)
        }
        #endif
    }
}
