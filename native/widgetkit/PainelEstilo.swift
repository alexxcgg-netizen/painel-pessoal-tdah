//
//  PainelEstilo.swift
//  PainelWidget (WidgetKit extension) - 2026-11-05, leva dos widgets nativos
//
//  O jeito Apple que o Alex votou no protótipo (artefato "Widgets e ícone", rodada 2): fundo branco no claro e
//  #1C1C1E no escuro, cores do sistema (que já mudam sozinhas entre claro/escuro), número grande em SF Rounded,
//  margem de 16 pt. No iOS 17+ o fundo vai em containerBackground (iOS 17.0+), que o próprio sistema tira no modo
//  vidro, no tingido e no StandBy; `.widgetAccentable()` marca o que pega a cor no modo tingido.
//  Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import SwiftUI
import UIKit
import WidgetKit

extension Color {
    /// Hex de 6 dígitos, sem "#" (ex: "41aa75"). Usado também pela atividade ao vivo (AtividadeCompromisso.swift).
    init(hex: String) {
        var valor: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&valor)
        let r = Double((valor & 0xFF0000) >> 16) / 255.0
        let g = Double((valor & 0x00FF00) >> 8) / 255.0
        let b = Double(valor & 0x0000FF) / 255.0
        self.init(red: r, green: g, blue: b)
    }
}

enum PainelEstilo {
    /// Fundo dos widgets da Apple: branco no claro, #1C1C1E no escuro.
    static let fundo = Color(UIColor { $0.userInterfaceStyle == .dark
        ? UIColor(red: 28 / 255, green: 28 / 255, blue: 30 / 255, alpha: 1)
        : .white })

    /// Trilho de barra/anel vazio (o "fill" cinza do sistema).
    static let trilho = Color(UIColor.tertiarySystemFill)

    /// Verde-limão do anel do Fitness (exercício), no fundo preto.
    static let fit1 = Color(red: 0x8b / 255, green: 0xe0 / 255, blue: 0)
    static let fit2 = Color(red: 0xc8 / 255, green: 1, blue: 0x3a / 255)

    static func numero(_ tamanho: CGFloat, _ peso: Font.Weight = .semibold) -> Font {
        .system(size: tamanho, weight: peso, design: .rounded).monospacedDigit()
    }

    private static let br = Locale(identifier: "pt_BR")

    /// 96.5 -> "96,5"; 150.0 -> "150".
    static func horas(_ valor: Double) -> String {
        let f = NumberFormatter()
        f.locale = br
        f.numberStyle = .decimal
        f.minimumFractionDigits = 0
        f.maximumFractionDigits = 1
        return f.string(from: NSNumber(value: valor)) ?? String(format: "%.1f", valor)
    }

    /// 1840 -> "1.840".
    static func milhar(_ valor: Double) -> String {
        let f = NumberFormatter()
        f.locale = br
        f.numberStyle = .decimal
        f.maximumFractionDigits = 0
        return f.string(from: NSNumber(value: valor)) ?? "\(Int(valor))"
    }

    /// "14:30" hoje, no relógio do iPhone.
    static func hojeAs(_ hhmm: String?, em dia: Date) -> Date? {
        guard let hhmm, hhmm.count == 5 else { return nil }
        let partes = hhmm.split(separator: ":").compactMap { Int($0) }
        guard partes.count == 2 else { return nil }
        return Calendar.current.date(bySettingHour: partes[0], minute: partes[1], second: 0, of: dia)
    }

    /// "seg., 9 nov." (o dia em que a conta vence).
    static func diaCurto(daqui dias: Int, de hoje: Date) -> String {
        let d = Calendar.current.date(byAdding: .day, value: dias, to: hoje) ?? hoje
        let f = DateFormatter()
        f.locale = br
        f.dateFormat = "EEE, d MMM"
        return f.string(from: d).lowercased()
    }

    /// Código do tempo (WMO, o mesmo do Open-Meteo) -> SF Symbol colorido do app Tempo.
    static func simboloTempo(_ codigo: Int?) -> String {
        switch codigo ?? -1 {
        case 0: return "sun.max.fill"
        case 1, 2: return "cloud.sun.fill"
        case 3: return "cloud.fill"
        case 45, 48: return "cloud.fog.fill"
        case 51...57: return "cloud.drizzle.fill"
        case 65, 82: return "cloud.heavyrain.fill"
        case 61...67, 80...81: return "cloud.rain.fill"
        case 71...77, 85, 86: return "cloud.snow.fill"
        case 95...99: return "cloud.bolt.rain.fill"
        default: return "cloud.sun.fill"
        }
    }
}

extension View {
    /// Fundo do widget. iOS 17.0+: containerBackground (o sistema tira no vidro/tingido/StandBy e cuida da margem).
    /// iOS 16: margem de 16 pt na mão e fundo comum.
    @ViewBuilder
    func fundoPainel<Fundo: View>(@ViewBuilder _ fundo: () -> Fundo) -> some View {
        let vista = fundo()
        if #available(iOSApplicationExtension 17.0, *) {
            self.containerBackground(for: .widget) { vista }
        } else {
            self.padding(16).frame(maxWidth: .infinity, maxHeight: .infinity).background(vista)
        }
    }

    func fundoPainel() -> some View {
        fundoPainel { PainelEstilo.fundo }
    }

    /// Tela bloqueada: o vidro é do sistema, o fundo é transparente (iOS 17.0+ exige a chamada mesmo assim).
    @ViewBuilder
    func fundoBloqueio() -> some View {
        if #available(iOSApplicationExtension 17.0, *) {
            self.containerBackground(Color.clear, for: .widget)
        } else {
            self
        }
    }
}

// MARK: - Peças repetidas

/// Ícone + nome no topo do widget, na cor do assunto (como Lembretes/Tempo).
struct CabecalhoWidget: View {
    let simbolo: String
    let titulo: String
    let cor: Color

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: simbolo)
                .font(.system(size: 13, weight: .semibold))
                .widgetAccentable()
            Text(titulo)
                .font(.system(size: 14, weight: .semibold))
                .lineLimit(1)
        }
        .foregroundStyle(cor)
    }
}

/// Bolinha colorida com símbolo (Lembretes, conta).
struct BolaSimbolo: View {
    let simbolo: String
    let cor: Color
    var tamanho: CGFloat = 30

    var body: some View {
        ZStack {
            Circle().fill(cor).widgetAccentable()
            Image(systemName: simbolo)
                .font(.system(size: tamanho * 0.52, weight: .bold))
                .foregroundStyle(.white)
        }
        .frame(width: tamanho, height: tamanho)
    }
}

/// Barra fininha de progresso (horas de voo).
struct BarraFina: View {
    let fracao: Double
    let cor: Color

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(PainelEstilo.trilho)
                Capsule().fill(cor)
                    .frame(width: max(6, geo.size.width * min(max(fracao, 0), 1)))
                    .widgetAccentable()
            }
        }
        .frame(height: 6)
    }
}

/// Enquanto o widget ainda não tem o token: o código que o app confirma (rotas/widget_ios.py).
struct TelaParear: View {
    let codigo: String
    var grande = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            CabecalhoWidget(simbolo: "lock.open.fill", titulo: "Painel", cor: .blue)
            Spacer(minLength: 2)
            Text("Abre o app e confirma")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(.secondary)
            Text(codigo.map(String.init).joined(separator: " "))
                .font(PainelEstilo.numero(grande ? 44 : 34))
                .minimumScaleFactor(0.7)
                .lineLimit(1)
                .widgetAccentable()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }
}

/// Sem dado nenhum ainda (nem cache): a mensagem curta do que fazer.
struct TelaAviso: View {
    let mensagem: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            CabecalhoWidget(simbolo: "exclamationmark.circle.fill", titulo: "Painel", cor: .orange)
            Spacer(minLength: 2)
            Text(mensagem)
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(.secondary)
                .lineLimit(3)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }
}

/// Casca comum: pareando / aviso / conteúdo, sempre com o fundo certo (o branco/#1C1C1E, ou um próprio).
struct CascaWidget<Conteudo: View, Fundo: View>: View {
    let carga: Carga
    let fundo: Fundo
    let conteudo: (PainelWidgetPayload) -> Conteudo

    init(carga: Carga, @ViewBuilder conteudo: @escaping (PainelWidgetPayload) -> Conteudo) where Fundo == Color {
        self.carga = carga
        self.fundo = PainelEstilo.fundo
        self.conteudo = conteudo
    }

    init(carga: Carga, fundo: Fundo, @ViewBuilder conteudo: @escaping (PainelWidgetPayload) -> Conteudo) {
        self.carga = carga
        self.fundo = fundo
        self.conteudo = conteudo
    }

    var body: some View {
        Group {
            switch carga {
            case .dados(let p): conteudo(p)
            case .parear(let codigo): TelaParear(codigo: codigo)
            case .erro(let mensagem): TelaAviso(mensagem: mensagem)
            }
        }
        .fundoPainel { fundo }
    }
}
