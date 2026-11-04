//
//  Localizacao.swift
//  Leva "onde eu estou" (2026-11-04, docs/briefings/2026-11-04-onde-eu-estou.md)
//
//  O iPhone avisa o painel quando o Alex chega num lugar e fica, e quando sai dele
//  (CLLocationManager.startMonitoringVisits, autorização "Sempre"). O iOS acorda o app mesmo
//  fechado pra entregar a visita; por isso o gerente nasce no didFinishLaunching (AppDelegate).
//  Nada de startUpdatingLocation contínuo (bateria): só as visitas.
//
//  Cada visita vai pra POST /api/localizacao/visita com o token do widget no header (nunca na
//  URL). Sem rede ou PC desligado: fica numa fila no UserDefaults (até 50, a mais velha sai) e vai
//  quando der (próxima visita ou quando o app abre).
//

import CoreLocation
import SwiftUI
import UIKit

final class Localizacao: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = Localizacao()
    static let chaveFila = "painel_visitas_fila"
    static let maxFila = 50

    @Published private(set) var status: CLAuthorizationStatus = .notDetermined
    @Published private(set) var pendentes = 0

    private let gerente = CLLocationManager()
    private var enviando = false
    private let iso = ISO8601DateFormatter()

    private override init() {
        super.init()
        gerente.delegate = self
        status = gerente.authorizationStatus
        pendentes = lerFila().count
    }

    /// AppDelegate chama no launch (inclusive quando o iOS relança o app em segundo plano por uma visita).
    func iniciar() {
        if gerente.authorizationStatus == .authorizedAlways {
            gerente.startMonitoringVisits()
        }
        enviarFila()
    }

    /// Botão da tela Configurar. Negada/bloqueada: só os Ajustes do iPhone mudam.
    func pedirPermissao() {
        switch gerente.authorizationStatus {
        case .notDetermined, .authorizedWhenInUse:
            gerente.requestAlwaysAuthorization()
        default:
            if let url = URL(string: UIApplication.openSettingsURLString) {
                UIApplication.shared.open(url)
            }
        }
    }

    var descricaoStatus: String {
        switch status {
        case .authorizedAlways: return "Sempre"
        case .authorizedWhenInUse: return "Só com o app aberto"
        case .denied: return "Negada"
        case .restricted: return "Bloqueada"
        case .notDetermined: return "Ainda não pedida"
        @unknown default: return "Desconhecida"
        }
    }

    // MARK: CLLocationManagerDelegate

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let novo = manager.authorizationStatus
        DispatchQueue.main.async { self.status = novo }
        if novo == .authorizedAlways {
            manager.startMonitoringVisits()
        } else {
            manager.stopMonitoringVisits()
        }
    }

    func locationManager(_ manager: CLLocationManager, didVisit visit: CLVisit) {
        let c = visit.coordinate
        guard CLLocationCoordinate2DIsValid(c) else { return }
        let chegada = visit.arrivalDate == Date.distantPast ? "" : iso.string(from: visit.arrivalDate)
        let saida = visit.departureDate == Date.distantFuture ? "" : iso.string(from: visit.departureDate)
        if chegada.isEmpty && saida.isEmpty { return }
        let item: [String: Any] = [
            "id": UUID().uuidString,
            "lat": (c.latitude * 10000).rounded() / 10000,
            "lon": (c.longitude * 10000).rounded() / 10000,
            "precisao": max(0, visit.horizontalAccuracy),
            "chegada": chegada,
            "saida": saida,
        ]
        DispatchQueue.main.async {
            self.enfileirar(item)
            self.enviarFila()
            AoVivo.shared.sincronizar()  // chegou/saiu de um lugar: passo da atividade ao vivo (AoVivo.swift)
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {}

    // MARK: Fila (sempre na main thread)

    private func lerFila() -> [[String: Any]] {
        Ajustes.defaults.array(forKey: Localizacao.chaveFila) as? [[String: Any]] ?? []
    }

    private func gravarFila(_ fila: [[String: Any]]) {
        Ajustes.defaults.set(fila, forKey: Localizacao.chaveFila)
        pendentes = fila.count
    }

    private func enfileirar(_ item: [String: Any]) {
        var fila = lerFila()
        fila.append(item)
        if fila.count > Localizacao.maxFila {
            fila.removeFirst(fila.count - Localizacao.maxFila)
        }
        gravarFila(fila)
    }

    private func tirarDaFila(_ id: String) {
        gravarFila(lerFila().filter { ($0["id"] as? String) != id })
    }

    /// Manda a fila em ordem, uma por vez. Para no primeiro erro de rede/servidor (tenta depois).
    func enviarFila() {
        guard !enviando, let base = URL(string: Ajustes.url), base.scheme != nil, !Ajustes.token.isEmpty,
              let primeiro = lerFila().first, let id = primeiro["id"] as? String else { return }
        enviando = true
        let app = UIApplication.shared
        var tarefa: UIBackgroundTaskIdentifier = .invalid
        tarefa = app.beginBackgroundTask(withName: "painel-visita") {
            if tarefa != .invalid {
                app.endBackgroundTask(tarefa)
                tarefa = .invalid
            }
        }
        mandar(primeiro, base: base) { resultado in
            DispatchQueue.main.async {
                self.enviando = false
                switch resultado {
                case .enviado, .descartar:
                    self.tirarDaFila(id)
                    self.enviarFila()
                case .tentarDepois:
                    break
                }
                if tarefa != .invalid {
                    app.endBackgroundTask(tarefa)
                    tarefa = .invalid
                }
            }
        }
    }

    private enum Resultado {
        case enviado, descartar, tentarDepois
    }

    private func mandar(_ item: [String: Any], base: URL, fim: @escaping (Resultado) -> Void) {
        var pedido = URLRequest(url: base.appendingPathComponent("api/localizacao/visita"))
        pedido.httpMethod = "POST"
        pedido.setValue("application/json", forHTTPHeaderField: "Content-Type")
        pedido.setValue("Bearer \(Ajustes.token)", forHTTPHeaderField: "Authorization")
        pedido.timeoutInterval = 20
        var corpo: [String: Any] = [
            "lat": item["lat"] ?? 0,
            "lon": item["lon"] ?? 0,
            "precisao": item["precisao"] ?? NSNull(),
        ]
        for chave in ["chegada", "saida"] {
            let valor = item[chave] as? String ?? ""
            corpo[chave] = valor.isEmpty ? NSNull() : valor
        }
        guard let dados = try? JSONSerialization.data(withJSONObject: corpo) else {
            fim(.descartar)
            return
        }
        pedido.httpBody = dados
        URLSession.shared.dataTask(with: pedido) { _, resposta, erro in
            let status = (resposta as? HTTPURLResponse)?.statusCode ?? 0
            if erro != nil || status == 0 {
                fim(.tentarDepois)
            } else if (200..<300).contains(status) {
                fim(.enviado)
            } else if status == 400 {
                fim(.descartar)  // dado que o painel nunca vai aceitar: não trava a fila
            } else {
                fim(.tentarDepois)  // 401 (token), 403 (modo visitante), 5xx: guarda
            }
        }.resume()
    }
}

/// Seção da tela Configurar: estado da permissão e o botão de pedir.
struct SecaoOndeEstou: View {
    @ObservedObject private var localizacao = Localizacao.shared

    private var rotuloBotao: String {
        let podePedir = localizacao.status == .notDetermined || localizacao.status == .authorizedWhenInUse
        return podePedir ? "Permitir “Sempre”" : "Abrir Ajustes do iPhone"
    }

    var body: some View {
        Section {
            HStack {
                Text("Localização")
                Spacer()
                Text(localizacao.descricaoStatus).foregroundColor(.secondary)
            }
            if localizacao.status != .authorizedAlways {
                Button(rotuloBotao) {
                    localizacao.pedirPermissao()
                }
            }
            if localizacao.pendentes > 0 {
                HStack {
                    Text("Esperando o painel")
                    Spacer()
                    Text("\(localizacao.pendentes)").foregroundColor(.secondary)
                }
            }
        } header: {
            Text("Onde eu estou")
        } footer: {
            Text("Com “Sempre”, o iPhone avisa o painel quando tu chega e sai de um lugar (mecânico, casa…). Só o lugar onde tu parou, nunca o caminho.")
        }
    }
}
