// Probador de Audios — app de Mac
// Abre una ventana pequeña que muestra el avance, arranca el servidor local
// (iniciar.sh) y abre la app en el navegador. Al salir, detiene el servidor.
import Cocoa

let nombreApp = "Probador de Audios"

final class AppDelegate: NSObject, NSApplicationDelegate {
    var ventana: NSWindow!
    let titulo = NSTextField(labelWithString: nombreApp)
    let estado = NSTextField(wrappingLabelWithString: "Iniciando…")
    let detalle = NSTextField(wrappingLabelWithString: "")
    let spinner = NSProgressIndicator()
    let botonAbrir = NSButton(title: "Abrir en el navegador", target: nil, action: nil)
    let botonRegistro = NSButton(title: "Ver registro", target: nil, action: nil)
    let botonReintentar = NSButton(title: "Reintentar", target: nil, action: nil)

    var proceso: Process?
    var tuberiaEntrada: Pipe?
    var pendiente = Data()
    var url: URL?
    var listo = false
    var saliendo = false
    var registro: FileHandle?

    let datosApp = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/ProbadorAudios")
    let archivoRegistro = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Logs/ProbadorAudios.log")

    // MARK: - Ciclo de vida

    func applicationDidFinishLaunching(_ notification: Notification) {
        construirMenu()
        construirVentana()
        abrirRegistro()
        iniciarServidor()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false  // la app sigue funcionando aunque se cierre la ventana
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        ventana.makeKeyAndOrderFront(nil)
        if listo { abrirNavegador(nil) }
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        detenerServidor()
    }

    // MARK: - Interfaz

    func construirVentana() {
        ventana = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 460, height: 300),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered, defer: false)
        ventana.title = nombreApp
        ventana.isReleasedWhenClosed = false
        ventana.center()

        let icono = NSImageView()
        icono.image = NSApp.applicationIconImage
        icono.imageScaling = .scaleProportionallyUpOrDown
        icono.translatesAutoresizingMaskIntoConstraints = false
        icono.widthAnchor.constraint(equalToConstant: 72).isActive = true
        icono.heightAnchor.constraint(equalToConstant: 72).isActive = true

        titulo.font = NSFont.systemFont(ofSize: 18, weight: .semibold)
        titulo.alignment = .center
        for campo in [estado, detalle] {
            campo.alignment = .center
            campo.preferredMaxLayoutWidth = 400
        }
        estado.font = NSFont.systemFont(ofSize: 13)
        detalle.font = NSFont.systemFont(ofSize: 11)
        detalle.textColor = .secondaryLabelColor

        spinner.style = .spinning
        spinner.controlSize = .regular
        spinner.isDisplayedWhenStopped = false
        spinner.startAnimation(nil)

        botonAbrir.target = self
        botonAbrir.action = #selector(abrirNavegador(_:))
        botonAbrir.bezelStyle = .rounded
        botonAbrir.keyEquivalent = "\r"
        botonAbrir.isHidden = true
        botonRegistro.target = self
        botonRegistro.action = #selector(verRegistro(_:))
        botonRegistro.bezelStyle = .rounded
        botonRegistro.isHidden = true
        botonReintentar.target = self
        botonReintentar.action = #selector(reintentar(_:))
        botonReintentar.bezelStyle = .rounded
        botonReintentar.isHidden = true

        let botones = NSStackView(views: [botonRegistro, botonReintentar, botonAbrir])
        botones.orientation = .horizontal
        botones.spacing = 10

        let pila = NSStackView(views: [icono, titulo, estado, spinner, detalle, botones])
        pila.orientation = .vertical
        pila.alignment = .centerX
        pila.spacing = 10
        pila.edgeInsets = NSEdgeInsets(top: 24, left: 24, bottom: 22, right: 24)
        pila.translatesAutoresizingMaskIntoConstraints = false

        let contenido = NSView()
        contenido.addSubview(pila)
        NSLayoutConstraint.activate([
            pila.leadingAnchor.constraint(equalTo: contenido.leadingAnchor),
            pila.trailingAnchor.constraint(equalTo: contenido.trailingAnchor),
            pila.topAnchor.constraint(equalTo: contenido.topAnchor),
            pila.bottomAnchor.constraint(equalTo: contenido.bottomAnchor),
            contenido.widthAnchor.constraint(equalToConstant: 460),
        ])
        ventana.contentView = contenido
        ventana.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func construirMenu() {
        let barra = NSMenu()

        let itemApp = NSMenuItem()
        barra.addItem(itemApp)
        let menuApp = NSMenu()
        menuApp.addItem(withTitle: "Acerca de \(nombreApp)",
                        action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        menuApp.addItem(.separator())
        menuApp.addItem(item("Abrir en el navegador", #selector(abrirNavegador(_:)), "o"))
        menuApp.addItem(item("Mostrar ventana", #selector(mostrarVentana(_:)), "1"))
        menuApp.addItem(item("Ver registro", #selector(verRegistro(_:)), ""))
        menuApp.addItem(.separator())
        menuApp.addItem(item("Desinstalar \(nombreApp)…", #selector(desinstalar(_:)), ""))
        menuApp.addItem(.separator())
        menuApp.addItem(withTitle: "Ocultar \(nombreApp)", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        menuApp.addItem(withTitle: "Salir de \(nombreApp)", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        itemApp.submenu = menuApp

        let itemVentana = NSMenuItem()
        barra.addItem(itemVentana)
        let menuVentana = NSMenu(title: "Ventana")
        menuVentana.addItem(withTitle: "Cerrar", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        menuVentana.addItem(withTitle: "Minimizar", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        itemVentana.submenu = menuVentana

        NSApp.mainMenu = barra
    }

    func item(_ titulo: String, _ accion: Selector, _ tecla: String) -> NSMenuItem {
        let i = NSMenuItem(title: titulo, action: accion, keyEquivalent: tecla)
        i.target = self
        return i
    }

    func mostrar(_ texto: String, detalle d: String? = nil) {
        estado.stringValue = texto
        if let d = d { detalle.stringValue = d }
    }

    // MARK: - Servidor

    func abrirRegistro() {
        let fm = FileManager.default
        try? fm.createDirectory(at: archivoRegistro.deletingLastPathComponent(), withIntermediateDirectories: true)
        fm.createFile(atPath: archivoRegistro.path, contents: nil)  // empieza limpio en cada arranque
        registro = try? FileHandle(forWritingTo: archivoRegistro)
    }

    func iniciarServidor() {
        guard let script = Bundle.main.url(forResource: "iniciar", withExtension: "sh") else {
            mostrarError("Falta un archivo de la app. Vuelve a descargarla.")
            return
        }
        listo = false
        url = nil
        pendiente = Data()
        spinner.startAnimation(nil)
        botonAbrir.isHidden = true
        botonReintentar.isHidden = true
        botonRegistro.isHidden = true
        mostrar("Iniciando…", detalle: "")

        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = [script.path]
        var entorno = ProcessInfo.processInfo.environment
        entorno["PROBADOR_VIGILAR_STDIN"] = "1"
        entorno["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        p.environment = entorno

        let salida = Pipe()
        let entrada = Pipe()
        p.standardOutput = salida
        p.standardError = salida
        p.standardInput = entrada
        tuberiaEntrada = entrada

        salida.fileHandleForReading.readabilityHandler = { [weak self] h in
            let datos = h.availableData
            if datos.isEmpty {
                h.readabilityHandler = nil
                return
            }
            DispatchQueue.main.async { self?.recibir(datos) }
        }
        p.terminationHandler = { [weak self] pr in
            let codigo = pr.terminationStatus
            DispatchQueue.main.async { self?.termino(codigo) }
        }
        do {
            try p.run()
            proceso = p
        } catch {
            mostrarError("No se pudo iniciar: \(error.localizedDescription)")
        }
    }

    func recibir(_ datos: Data) {
        registro?.write(datos)
        pendiente.append(datos)
        while let fin = pendiente.firstIndex(of: 10) {
            let linea = String(decoding: pendiente[pendiente.startIndex..<fin], as: UTF8.self)
            pendiente = Data(pendiente[pendiente.index(after: fin)...])
            procesar(linea.trimmingCharacters(in: .whitespacesAndNewlines))
        }
    }

    func procesar(_ linea: String) {
        if linea.isEmpty { return }
        if linea.hasPrefix("ESTADO:") {
            mostrar(String(linea.dropFirst(7)).trimmingCharacters(in: .whitespaces), detalle: "")
        } else if linea.hasPrefix("ERROR:") {
            mostrarError(String(linea.dropFirst(6)).trimmingCharacters(in: .whitespaces))
        } else if linea.hasPrefix("PROBADOR_URL=") {
            url = URL(string: String(linea.dropFirst("PROBADOR_URL=".count)))
            esperarServidor(intentos: 120)
        } else if !listo {
            // Mostrar la última línea de avance (p. ej. "Installed 45 packages")
            let corta = linea.count > 90 ? String(linea.prefix(90)) + "…" : linea
            detalle.stringValue = corta
        }
    }

    func esperarServidor(intentos: Int) {
        guard let base = url, let ping = URL(string: "/api/ping", relativeTo: base) else { return }
        var pedido = URLRequest(url: ping)
        pedido.timeoutInterval = 2
        URLSession.shared.dataTask(with: pedido) { [weak self] datos, _, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if let d = datos, String(decoding: d, as: UTF8.self).contains("probador-audios") {
                    self.servidorListo()
                } else if intentos > 0 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                        self.esperarServidor(intentos: intentos - 1)
                    }
                } else {
                    self.mostrarError("La app no respondió a tiempo.")
                }
            }
        }.resume()
    }

    func servidorListo() {
        if listo { return }
        listo = true
        spinner.stopAnimation(nil)
        mostrar("La app está abierta en tu navegador.",
                detalle: "Puedes cerrar esta ventana; la app sigue funcionando.\nPara salir usa ⌘Q.")
        botonAbrir.isHidden = false
        abrirNavegador(nil)
    }

    func termino(_ codigo: Int32) {
        proceso = nil
        if saliendo { return }
        if listo && codigo == 0 {
            // Ya había otra copia funcionando; esta solo abrió el navegador.
            return
        }
        mostrarError("La app se cerró inesperadamente (código \(codigo)).")
    }

    func mostrarError(_ texto: String) {
        spinner.stopAnimation(nil)
        mostrar(texto, detalle: "Si es la primera vez, revisa tu conexión a internet y pulsa Reintentar.")
        botonReintentar.isHidden = false
        botonRegistro.isHidden = false
        botonAbrir.isHidden = true
        ventana.makeKeyAndOrderFront(nil)
    }

    func detenerServidor() {
        saliendo = true
        try? tuberiaEntrada?.fileHandleForWriting.close()  // el servidor termina al cerrarse
        guard let p = proceso, p.isRunning else { return }
        p.terminate()
        let limite = Date().addingTimeInterval(4)
        while p.isRunning && Date() < limite { usleep(100_000) }
        if p.isRunning { kill(p.processIdentifier, SIGKILL) }
    }

    // MARK: - Acciones

    @objc func abrirNavegador(_ sender: Any?) {
        guard listo, let u = url else { return }
        NSWorkspace.shared.open(u)
    }

    @objc func mostrarVentana(_ sender: Any?) {
        ventana.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func verRegistro(_ sender: Any?) {
        NSWorkspace.shared.open(archivoRegistro)
    }

    @objc func reintentar(_ sender: Any?) {
        saliendo = false
        abrirRegistro()
        iniciarServidor()
    }

    @objc func desinstalar(_ sender: Any?) {
        let fm = FileManager.default
        let hub = fm.homeDirectoryForCurrentUser.appendingPathComponent(".cache/huggingface/hub")
        var aBorrar: [URL] = []
        if fm.fileExists(atPath: datosApp.path) { aBorrar.append(datosApp) }
        if let viejos = try? fm.contentsOfDirectory(at: hub, includingPropertiesForKeys: nil) {
            aBorrar += viejos.filter {
                $0.lastPathComponent.hasPrefix("models--Systran--faster-whisper-") ||
                $0.lastPathComponent.hasPrefix("models--mobiuslabsgmbh--faster-whisper-")
            }
        }
        let total = aBorrar.reduce(Int64(0)) { $0 + tamano($1) }
        let texto = ByteCountFormatter.string(fromByteCount: total, countStyle: .file)

        let alerta = NSAlert()
        alerta.alertStyle = .warning
        alerta.messageText = "¿Desinstalar \(nombreApp)?"
        alerta.informativeText = "Se borrarán el modelo de voz, los componentes y los proyectos guardados en la app (\(texto)). " +
            "Tus archivos de audio originales no se tocan.\n\nLa app se moverá a la Papelera."
        alerta.addButton(withTitle: "Desinstalar")
        alerta.addButton(withTitle: "Cancelar")
        if #available(macOS 11.0, *) { alerta.buttons.first?.hasDestructiveAction = true }
        guard alerta.runModal() == .alertFirstButtonReturn else { return }

        mostrar("Desinstalando…", detalle: "")
        spinner.startAnimation(nil)
        detenerServidor()
        for u in aBorrar { try? fm.removeItem(at: u) }
        try? fm.removeItem(at: archivoRegistro)

        NSWorkspace.shared.recycle([Bundle.main.bundleURL]) { _, error in
            DispatchQueue.main.async {
                let fin = NSAlert()
                fin.messageText = "Listo"
                fin.informativeText = error == nil
                    ? "\(nombreApp) se desinstaló y está en la Papelera."
                    : "Se borraron el modelo y los componentes. Arrastra \(nombreApp) a la Papelera para terminar."
                fin.runModal()
                NSApp.terminate(nil)
            }
        }
    }

    func tamano(_ carpeta: URL) -> Int64 {
        var total: Int64 = 0
        let claves: [URLResourceKey] = [.totalFileAllocatedSizeKey, .isRegularFileKey]
        guard let e = FileManager.default.enumerator(at: carpeta, includingPropertiesForKeys: claves) else { return 0 }
        for case let u as URL in e {
            if let v = try? u.resourceValues(forKeys: Set(claves)), v.isRegularFile == true {
                total += Int64(v.totalFileAllocatedSize ?? 0)
            }
        }
        return total
    }
}

let app = NSApplication.shared
let delegado = AppDelegate()
app.delegate = delegado
app.setActivationPolicy(.regular)
app.run()
