import Foundation

enum DaemonError: LocalizedError {
    case executableNotFound
    case startupFailed(String)

    var errorDescription: String? {
        switch self {
        case .executableNotFound:
            "Dispatch daemon executable was not found"
        case .startupFailed(let reason) where !reason.isEmpty:
            "Dispatch daemon did not become ready — \(reason)"
        case .startupFailed:
            "Dispatch daemon did not become ready"
        }
    }
}

actor DaemonManager {
    static let shared = DaemonManager()

    private var process: Process?
    /// daemon이 죽으면서 남긴 말. 버리면 화면에 이유 없는 실패만 남는다.
    private var errorPipe: Pipe?
    private let healthURL = URL(string: "http://127.0.0.1:8790/health")!

    func ensureRunning() async throws {
        if await isHealthy() { return }
        if let process, process.isRunning {
            try await waitUntilHealthy()
            return
        }
        let executable = try daemonExecutable()
        let child = Process()
        child.executableURL = executable
        child.arguments = ["daemon", "--send"]
        child.currentDirectoryURL = projectDirectory(for: executable)
        let errors = Pipe()
        child.standardOutput = FileHandle.nullDevice
        child.standardError = errors
        try child.run()
        process = child
        errorPipe = errors
        try await waitUntilHealthy()
    }

    /// 이미 죽은 프로세스의 파이프만 읽는다. 살아 있는 동안 읽으면 daemon이
    /// 로그를 쏟는 속도에 맞춰 여기가 멈춘다.
    private func startupFailure() -> String {
        guard let process, !process.isRunning, let errorPipe else { return "" }
        let data = errorPipe.fileHandleForReading.availableData
        let text = String(decoding: data, as: UTF8.self)
        return text.split(separator: "\n").last.map(String.init)?
            .trimmingCharacters(in: .whitespaces) ?? ""
    }

    private func isHealthy() async -> Bool {
        var request = URLRequest(url: healthURL)
        request.timeoutInterval = 1
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    private func waitUntilHealthy() async throws {
        for _ in 0..<50 {
            if await isHealthy() { return }
            if let process, !process.isRunning { break }
            try await Task.sleep(for: .milliseconds(200))
        }
        throw DaemonError.startupFailed(startupFailure())
    }

    private func daemonExecutable() throws -> URL {
        let environment = ProcessInfo.processInfo.environment
        if let override = environment["DISPATCH_DAEMON_EXECUTABLE"] {
            let url = URL(fileURLWithPath: override)
            if FileManager.default.isExecutableFile(atPath: url.path) { return url }
        }
        let candidates = [
            Bundle.main.bundleURL
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appending(path: ".venv/bin/dispatch-node"),
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
                .appending(path: ".venv/bin/dispatch-node"),
        ]
        guard let found = candidates.first(where: {
            FileManager.default.isExecutableFile(atPath: $0.path)
        }) else {
            throw DaemonError.executableNotFound
        }
        return found
    }

    private func projectDirectory(for executable: URL) -> URL {
        executable
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
    }
}
