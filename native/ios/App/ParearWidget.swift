//
//  ParearWidget.swift
//  Painel (app) - 2026-11-05, leva dos widgets nativos
//
//  A assinatura grátis do Sideloadly corta o App Group: o widget não enxerga o token que o app guardou e pede
//  um código pro painel (POST /api/widget/parear, rotas/widget_ios.py). Aqui o app, que tem o token, vê o pedido
//  quando abre e pergunta "Liberar este widget?" com o mesmo código que o widget está mostrando. Liberou: o
//  painel entrega o token uma vez pro widget e o app manda os widgets se atualizarem na hora.
//

import Combine
import Foundation
import WidgetKit

@MainActor
final class ParearWidget: ObservableObject {
    static let shared = ParearWidget()

    @Published var mostrar = false
    @Published private(set) var codigo = ""

    /// "Agora não" vale até o app fechar (não pergunta de novo o mesmo código nessa abertura).
    private var recusados: Set<String> = []
    private var conferindo = false

    private func pedido(_ caminho: String, metodo: String = "GET", corpo: [String: Any]? = nil) -> URLRequest? {
        var base = Ajustes.url.trimmingCharacters(in: .whitespacesAndNewlines)
        let token = Ajustes.token
        guard !base.isEmpty, !token.isEmpty else { return nil }
        while base.hasSuffix("/") { base.removeLast() }
        guard let url = URL(string: base + caminho), url.scheme?.hasPrefix("http") == true else { return nil }
        var p = URLRequest(url: url)
        p.httpMethod = metodo
        p.timeoutInterval = 10
        p.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let corpo, let dados = try? JSONSerialization.data(withJSONObject: corpo) {
            p.httpBody = dados
            p.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return p
    }

    private func pendentes() async -> [String] {
        guard let p = pedido("/api/widget/parear/pendentes"),
              let r = try? await URLSession.shared.data(for: p),
              (r.1 as? HTTPURLResponse)?.statusCode == 200,
              let json = (try? JSONSerialization.jsonObject(with: r.0)) as? [String: Any],
              let lista = json["pendentes"] as? [[String: Any]] else { return [] }
        return lista.compactMap { $0["codigo"] as? String }
    }

    /// Ao abrir o app: tem widget pedindo? Se não tem, acorda os widgets (o que ainda não pediu, pede agora)
    /// e olha de novo uma vez daqui a 6 s.
    func conferir() {
        guard !conferindo, !mostrar, !Ajustes.token.isEmpty else { return }
        conferindo = true
        Task {
            var achado = await pendentes().first { !recusados.contains($0) }
            if achado == nil {
                WidgetCenter.shared.reloadAllTimelines()
                try? await Task.sleep(nanoseconds: 6_000_000_000)
                achado = await pendentes().first { !recusados.contains($0) }
            }
            conferindo = false
            if let achado {
                codigo = achado
                mostrar = true
            }
        }
    }

    func liberar() {
        let c = codigo
        Task {
            if let p = pedido("/api/widget/parear/liberar", metodo: "POST", corpo: ["codigo": c]) {
                _ = try? await URLSession.shared.data(for: p)
            }
            WidgetCenter.shared.reloadAllTimelines()
            // outro widget pode ter pedido junto (cada um no seu tempo): confere de novo
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            conferir()
        }
    }

    func agoraNao() {
        recusados.insert(codigo)
    }

    /// Código com espaço entre os números, igual o widget mostra ("4 8 1 7").
    var codigoEspacado: String { codigo.map(String.init).joined(separator: " ") }
}
