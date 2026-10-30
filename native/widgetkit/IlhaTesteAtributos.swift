//
//  IlhaTesteAtributos.swift
//  Compartilhado entre o app (que liga a atividade) e o widget (que desenha) - 2026-10-30
//
//  Atividade de teste da tela "Gerar relatório": prova se a Dynamic Island funciona neste iPhone
//  com a assinatura grátis. O iPhone conta o tempo sozinho, sem rede.
//

import ActivityKit
import Foundation

struct IlhaTesteAtributos: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var inicio: Date
        var fim: Date
    }

    var titulo: String
}
