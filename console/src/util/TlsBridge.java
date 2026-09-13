package util;

import com.sun.net.httpserver.*;
import javax.net.ssl.*;
import java.io.*;
import java.net.*;
import java.security.KeyStore;
import java.security.cert.X509Certificate;
import java.util.*;

public class TlsBridge {
    private static volatile String targetHost = "127.0.0.1";
    private static volatile int targetPort = 443;
    private static SSLSocketFactory sslSocketFactory;
    private static final Map<Integer, TcpForwarder> tcpForwarders = new java.util.concurrent.ConcurrentHashMap<>();
    private static volatile boolean redfishUnsupported = false;

    public static synchronized void ensureTcpForwarder(int port) {
        if (port <= 0 || port > 65535) return;
        if (!tcpForwarders.containsKey(port)) {
            TcpForwarder f = new TcpForwarder(port);
            tcpForwarders.put(port, f);
            Thread t = new Thread(f, "TcpForwarder-" + port);
            t.setDaemon(true);
            t.start();
        }
    }

    private static class TcpForwarder implements Runnable {
        private final int port;
        private ServerSocket serverSocket;
        TcpForwarder(int port) { this.port = port; }

        @Override
        public void run() {
            try {
                serverSocket = new ServerSocket();
                serverSocket.setReuseAddress(true);
                serverSocket.bind(new InetSocketAddress("127.0.0.1", port));
                System.out.println("[TlsBridge] TCP Stream Forwarder active on 127.0.0.1:" + port + " -> " + targetHost + ":" + port);
                while (!serverSocket.isClosed()) {
                    Socket clientSocket = serverSocket.accept();
                    clientSocket.setTcpNoDelay(true);
                    String host = targetHost;
                    Thread tunnelThread = new Thread(() -> handleConnection(clientSocket, host, port), "TcpTunnel-" + port);
                    tunnelThread.setDaemon(true);
                    tunnelThread.start();
                }
            } catch (IOException e) {
                System.err.println("[TlsBridge] TCP Forwarder notice on port " + port + ": " + e.getMessage());
            }
        }

        private void handleConnection(Socket clientSocket, String host, int destPort) {
            try {
                Socket targetSocket = new Socket();
                targetSocket.setTcpNoDelay(true);
                targetSocket.connect(new InetSocketAddress(host, destPort), 8000);
                System.out.println("[TlsBridge] TCP Tunnel connected: 127.0.0.1:" + port + " <-> " + host + ":" + destPort);

                Thread t1 = new Thread(() -> pipe(clientSocket, targetSocket), "PipeClientToTarget-" + destPort);
                Thread t2 = new Thread(() -> pipe(targetSocket, clientSocket), "PipeTargetToClient-" + destPort);
                t1.setDaemon(true);
                t2.setDaemon(true);
                t1.start();
                t2.start();
            } catch (Exception e) {
                System.err.println("[TlsBridge] Failed to connect TCP tunnel to " + host + ":" + destPort + ": " + e.getMessage());
                try { clientSocket.close(); } catch (Exception ignored) {}
            }
        }

        private void pipe(Socket inSock, Socket outSock) {
            try (InputStream in = inSock.getInputStream();
                 OutputStream out = outSock.getOutputStream()) {
                byte[] buf = new byte[32768];
                int n;
                while ((n = in.read(buf)) != -1) {
                    out.write(buf, 0, n);
                    out.flush();
                }
            } catch (Exception ignored) {}
            finally {
                try { inSock.close(); } catch (Exception ignored) {}
                try { outSock.close(); } catch (Exception ignored) {}
            }
        }
    }

    public static void main(String[] args) {
        int listenPort = 8089;
        int httpsPort = 8443;
        if (args.length >= 1) {
            targetHost = args[0];
        }
        if (args.length >= 2 && args[1].matches("\\d+")) {
            targetPort = Integer.parseInt(args[1]);
        }
        if (args.length >= 3 && args[2].matches("\\d+")) {
            listenPort = Integer.parseInt(args[2]);
        }
        if (args.length >= 4 && args[3].matches("\\d+")) {
            httpsPort = Integer.parseInt(args[3]);
        }

        try {
            initSsl();

            // Start default TCP forwarders for iLO remote console & virtual media
            ensureTcpForwarder(17990);
            ensureTcpForwarder(17988);

            HttpHandler targetHandler = exchange -> {
                String query = exchange.getRequestURI().getQuery();
                if (query != null) {
                    for (String param : query.split("&")) {
                        String[] pair = param.split("=", 2);
                        if (pair.length == 2) {
                            if (pair[0].equalsIgnoreCase("host")) {
                                String newHost = pair[1].trim();
                                if (!newHost.equalsIgnoreCase(targetHost)) {
                                    staticCache.clear();
                                    redfishUnsupported = false;
                                    targetHost = newHost;
                                    startPrewarming(targetHost, targetPort);
                                }
                            }
                            if (pair[0].equalsIgnoreCase("port")) targetPort = Integer.parseInt(pair[1].trim());
                        }
                    }
                }
                String resp = "TARGET_SET:" + targetHost + ":" + targetPort;
                exchange.sendResponseHeaders(200, resp.getBytes().length);
                try (OutputStream os = exchange.getResponseBody()) { os.write(resp.getBytes()); }
            };

            HttpHandler shutdownHandler = exchange -> {
                String resp = "BRIDGE_SHUTDOWN_OK";
                byte[] bytes = resp.getBytes(java.nio.charset.StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(200, bytes.length);
                try (OutputStream os = exchange.getResponseBody()) { os.write(bytes); }
                new Thread(() -> {
                    try { Thread.sleep(100); } catch (InterruptedException ignored) {}
                    System.out.println("[TlsBridge] Clean shutdown requested via HTTP. Exiting.");
                    System.exit(0);
                }).start();
            };

            // 1. Plain HTTP Bridge (Port 8089) for Web Browsers (Chrome / Edge)
            HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", listenPort), 0);
            server.createContext("/__bridge_set_target", targetHandler);
            server.createContext("/__bridge_shutdown", shutdownHandler);
            final int finalPort = listenPort;
            server.createContext("/", exchange -> handleProxy(exchange, finalPort));
            server.setExecutor(java.util.concurrent.Executors.newCachedThreadPool());
            server.start();
            System.out.println("[TlsBridge] HTTP Bridge Running on http://127.0.0.1:" + listenPort + " -> https://" + targetHost + ":" + targetPort);

            // 2. HTTPS Bridge (Port 8443) for HPLOCONS & External HTTPS Clients
            try {
                InputStream is = TlsBridge.class.getResourceAsStream("/bridge.p12");
                if (is == null) {
                    File p12File = new File("console/bridge.p12");
                    if (!p12File.exists()) {
                        p12File = new File("bridge.p12");
                    }
                    if (p12File.exists()) is = new FileInputStream(p12File);
                }
                if (is != null) {
                    KeyStore ks = KeyStore.getInstance("PKCS12");
                    try (InputStream inStream = is) {
                        ks.load(inStream, "ilobridge".toCharArray());
                    }
                    KeyManagerFactory kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
                    kmf.init(ks, "ilobridge".toCharArray());
                    SSLContext serverSslContext = SSLContext.getInstance("TLS");
                    serverSslContext.init(kmf.getKeyManagers(), null, null);

                    HttpsServer httpsServer = HttpsServer.create(new InetSocketAddress("127.0.0.1", httpsPort), 0);
                    httpsServer.setHttpsConfigurator(new HttpsConfigurator(serverSslContext));
                    httpsServer.createContext("/__bridge_set_target", targetHandler);
                    httpsServer.createContext("/__bridge_shutdown", shutdownHandler);
                    final int finalHttpsPort = httpsPort;
                    httpsServer.createContext("/", exchange -> handleProxy(exchange, finalHttpsPort));
                    httpsServer.setExecutor(java.util.concurrent.Executors.newCachedThreadPool());
                    httpsServer.start();
                    System.out.println("[TlsBridge] HTTPS Bridge Running on https://127.0.0.1:" + httpsPort + " -> https://" + targetHost + ":" + targetPort);
                }
            } catch (Exception e) {
                System.err.println("[TlsBridge] Warning: Could not start HTTPS bridge listener: " + e.getMessage());
            }

            if (targetHost != null && !targetHost.isEmpty() && !targetHost.equals("127.0.0.1")) {
                startPrewarming(targetHost, targetPort);
            }

        } catch (Exception e) {
            System.err.println("[TlsBridge] Fatal Error: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }

    private static class CachedItem {
        final int code;
        final byte[] data;
        final Map<String, List<String>> headers;
        CachedItem(int code, byte[] data, Map<String, List<String>> headers) {
            this.code = code;
            this.data = data;
            this.headers = headers;
        }
    }
    private static final Map<String, CachedItem> staticCache = new java.util.concurrent.ConcurrentHashMap<>();

    private static void startPrewarming(String host, int port) {
        if (host == null || host.isEmpty() || host.equals("127.0.0.1")) return;
        Thread t = new Thread(() -> {
            try {
                Thread.sleep(400);
            } catch (InterruptedException ignored) {}

            String[] assets = new String[]{
                "/",
                "/html/login.html",
                "/html/blank.html",
                "/html/app.html",
                "/css/jquery-ui.css",
                "/css/eov.css",
                "/css/layout.css",
                "/css/tree.css",
                "/js/json2.js",
                "/js/jquery.js",
                "/js/jquery-ui.js",
                "/js/iLO.js",
                "/images/signin_logo.png",
                "/images/help.png",
                "/images/favicon.ico"
            };

            for (String asset : assets) {
                if (staticCache.containsKey(asset)) continue;
                try {
                    Thread.sleep(80);
                } catch (InterruptedException ignored) {}
                try {
                    URL url = new URL("https://" + host + ":" + port + asset);
                    HttpsURLConnection conn = (HttpsURLConnection) url.openConnection();
                    conn.setSSLSocketFactory(sslSocketFactory);
                    conn.setHostnameVerifier((h, s) -> true);
                    conn.setRequestMethod("GET");
                    conn.setConnectTimeout(4000);
                    conn.setReadTimeout(8000);
                    conn.setRequestProperty("Connection", "keep-alive");
                    int code = conn.getResponseCode();
                    if (code == 200) {
                        byte[] data;
                        try (InputStream in = conn.getInputStream()) {
                            data = in.readAllBytes();
                        }
                        if (asset.equals("/") || asset.equals("/index.html")) {
                            String html = new String(data, "UTF-8");
                            if (html.contains("<frame name=\"modalFrame\"") && !html.contains("src=\"html/login.html\"")) {
                                html = html.replace("<frame name=\"modalFrame\" id=\"modalFrame\"", "<frame name=\"modalFrame\" id=\"modalFrame\" src=\"html/login.html\"");
                                html = html.replace("<frame name=\"appFrame\" id=\"appFrame\"", "<frame name=\"appFrame\" id=\"appFrame\" src=\"html/blank.html\"");
                                html = html.replace("<frame name=\"appletFrame\" id=\"appletFrame\"", "<frame name=\"appletFrame\" id=\"appletFrame\" src=\"html/blank.html\"");
                            }
                            data = html.getBytes("UTF-8");
                        }
                        Map<String, List<String>> savedHeaders = new HashMap<>();
                        for (Map.Entry<String, List<String>> entry : conn.getHeaderFields().entrySet()) {
                            String k = entry.getKey();
                            if (k != null && !k.equalsIgnoreCase("Content-Length") && !k.equalsIgnoreCase("Transfer-Encoding") && !k.equalsIgnoreCase("Pragma") && !k.equalsIgnoreCase("Expires") && !k.equalsIgnoreCase("Cache-Control")) {
                                savedHeaders.put(k, new ArrayList<>(entry.getValue()));
                            }
                        }
                        staticCache.put(asset, new CachedItem(code, data, savedHeaders));
                    }
                } catch (Exception ignored) {}
            }
            System.out.println("[TlsBridge] Background prewarmed " + staticCache.size() + " static assets for " + host);
        });
        t.setDaemon(true);
        t.setName("iLO-Prewarmer");
        t.start();
    }

    private static void handleProxy(HttpExchange exchange, int localPort) throws IOException {
        String path = exchange.getRequestURI().toString();
        if (path.startsWith("/__bridge_set_target")) return;

        while (path.startsWith("//")) {
            path = path.substring(1);
        }
        if (path.isEmpty()) {
            path = "/";
        }

        String method = exchange.getRequestMethod();
        System.out.println("[TlsBridge " + localPort + "] " + method + " " + path);

        // 1. Check in-memory static cache (<0.5ms response time)
        boolean isStatic = "GET".equalsIgnoreCase(method) &&
            (path.endsWith(".js") || path.endsWith(".css") || path.endsWith(".png") || 
             path.endsWith(".gif") || path.endsWith(".ico") || path.endsWith(".jpg") || 
             path.endsWith(".jpeg") || path.endsWith(".svg") || path.endsWith(".swf") ||
             path.endsWith(".html") || path.endsWith(".htm") || path.equals("/") ||
             path.startsWith("/html/") || path.startsWith("/css/") || path.startsWith("/js/") || path.startsWith("/images/")) &&
            !path.startsWith("/json/") && !path.contains("session") && !path.contains("ribcl");

        if (isStatic) {
            CachedItem cached = staticCache.get(path);
            if (cached != null) {
                Headers respHeaders = exchange.getResponseHeaders();
                for (Map.Entry<String, List<String>> entry : cached.headers.entrySet()) {
                    String k = entry.getKey();
                    if (k != null && !k.equalsIgnoreCase("Content-Length") && !k.equalsIgnoreCase("Transfer-Encoding") && !k.equalsIgnoreCase("Pragma") && !k.equalsIgnoreCase("Expires") && !k.equalsIgnoreCase("Cache-Control")) {
                        respHeaders.put(k, entry.getValue());
                    }
                }
                respHeaders.set("Cache-Control", "public, max-age=31536000, immutable");
                exchange.sendResponseHeaders(cached.code, cached.data.length);
                try (OutputStream out = exchange.getResponseBody()) {
                    out.write(cached.data);
                }
                return;
            }
        }

        if (path.startsWith("/redfish/") && redfishUnsupported) {
            byte[] notFound = "{\"error\":\"Redfish not supported on legacy iLO\"}".getBytes("UTF-8");
            exchange.sendResponseHeaders(404, notFound.length);
            try (OutputStream out = exchange.getResponseBody()) { out.write(notFound); }
            return;
        }

        try {
            URL targetUrl = new URL("https://" + targetHost + ":" + targetPort + path);

            HttpsURLConnection conn = (HttpsURLConnection) targetUrl.openConnection();
            conn.setSSLSocketFactory(sslSocketFactory);
            conn.setHostnameVerifier((h, s) -> true);
            conn.setRequestMethod(method);
            conn.setDoInput(true);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(20000);

            // Forward request headers + enable keep-alive
            for (Map.Entry<String, List<String>> entry : exchange.getRequestHeaders().entrySet()) {
                String key = entry.getKey();
                if (!key.equalsIgnoreCase("Host") && !key.equalsIgnoreCase("Content-Length")) {
                    if (path.contains("login_session")) {
                        // iLO 3 firmware 1.94 rejects login with 500 Internal Server Error
                        // if OData-Version, Cookie, or X-Auth-Token headers are forwarded.
                        if (key.equalsIgnoreCase("OData-Version") ||
                            key.equalsIgnoreCase("Cookie") ||
                            key.equalsIgnoreCase("X-Auth-Token")) {
                            continue;
                        }
                    }
                    for (String val : entry.getValue()) {
                        conn.addRequestProperty(key, val);
                    }
                }
            }
            conn.setRequestProperty("Host", targetHost + ":" + targetPort);
            conn.setRequestProperty("Connection", "keep-alive");

            // Forward request body
            if ("POST".equalsIgnoreCase(method) || "PUT".equalsIgnoreCase(method)) {
                conn.setDoOutput(true);
                try (InputStream in = exchange.getRequestBody();
                     OutputStream out = conn.getOutputStream()) {
                    in.transferTo(out);
                }
            }

            int code = conn.getResponseCode();
            Headers respHeaders = exchange.getResponseHeaders();

            for (Map.Entry<String, List<String>> entry : conn.getHeaderFields().entrySet()) {
                String key = entry.getKey();
                if (key != null && !key.equalsIgnoreCase("Transfer-Encoding")) {
                    // Do not forward frame restriction headers so iLO UI can be embedded in iframe
                    if (key.equalsIgnoreCase("X-Frame-Options") || 
                        key.equalsIgnoreCase("Content-Security-Policy") ||
                        key.equalsIgnoreCase("Cross-Origin-Opener-Policy") ||
                        key.equalsIgnoreCase("Cross-Origin-Embedder-Policy")) {
                        continue;
                    }
                    for (String val : entry.getValue()) {
                        if (key.equalsIgnoreCase("Location")) {
                            // Rewrite redirects to local proxy
                            val = val.replace("https://" + targetHost + ":" + targetPort, "http://127.0.0.1:" + localPort);
                            val = val.replace("https://" + targetHost, "http://127.0.0.1:" + localPort);
                            val = val.replace("http://" + targetHost + ":" + targetPort, "http://127.0.0.1:" + localPort);
                            val = val.replace("http://" + targetHost, "http://127.0.0.1:" + localPort);
                        } else if (key.equalsIgnoreCase("Set-Cookie")) {
                            // Strip Secure, SameSite, and Domain flags so browser accepts cookie over http://127.0.0.1
                            val = val.replaceAll("(?i);\\s*Secure", "");
                            val = val.replaceAll("(?i);\\s*SameSite=[^;]+", "");
                            val = val.replaceAll("(?i);\\s*Domain=[^;]+", "");
                        }
                        respHeaders.add(key, val);
                    }
                }
            }

            // Read response body and ensure stream is closed so SSL connection returns to keep-alive pool
            byte[] data;
            try (InputStream respStream = (code >= 200 && code < 400) ? conn.getInputStream() : conn.getErrorStream()) {
                data = respStream != null ? respStream.readAllBytes() : new byte[0];
            }

            if (path.startsWith("/redfish/") && code == 404) {
                redfishUnsupported = true;
            }

            if (code == 200 && (path.contains("rc_info") || path.contains("RcInfo"))) {
                try {
                    String respStr = new String(data, "UTF-8");
                    java.util.regex.Matcher mRc = java.util.regex.Pattern.compile("\"rc_port\"\\s*:\\s*(\\d+)").matcher(respStr);
                    if (mRc.find()) {
                        ensureTcpForwarder(Integer.parseInt(mRc.group(1)));
                    }
                    java.util.regex.Matcher mVm = java.util.regex.Pattern.compile("\"vm_port\"\\s*:\\s*(\\d+)").matcher(respStr);
                    if (mVm.find()) {
                        ensureTcpForwarder(Integer.parseInt(mVm.group(1)));
                    }
                } catch (Exception ignored) {}
            }

            String contentType = conn.getContentType();
            if (contentType != null && contentType.toLowerCase().contains("text/html") && data.length > 0) {
                String html = new String(data, "UTF-8");
                if (html.contains("baseURL = baseURL.substring")) {
                    html = html.replace(
                        "baseURL = baseURL.substring(0,baseURL.lastIndexOf(\"/\")+1);",
                        "baseURL = window.location.origin + window.location.pathname.substring(0, window.location.pathname.lastIndexOf(\"/\") + 1);"
                    );
                }
                if (html.contains("<frame name=\"modalFrame\"") && !html.contains("src=\"html/login.html\"")) {
                    html = html.replace("<frame name=\"modalFrame\" id=\"modalFrame\"", "<frame name=\"modalFrame\" id=\"modalFrame\" src=\"html/login.html\"");
                    html = html.replace("<frame name=\"appFrame\" id=\"appFrame\"", "<frame name=\"appFrame\" id=\"appFrame\" src=\"html/blank.html\"");
                    html = html.replace("<frame name=\"appletFrame\" id=\"appletFrame\"", "<frame name=\"appletFrame\" id=\"appletFrame\" src=\"html/blank.html\"");
                }
                data = html.getBytes("UTF-8");
            }

            // Save static resources to cache
            if (isStatic && code == 200 && data.length > 0) {
                Map<String, List<String>> savedHeaders = new HashMap<>();
                for (Map.Entry<String, List<String>> entry : respHeaders.entrySet()) {
                    String k = entry.getKey();
                    if (k != null && !k.equalsIgnoreCase("Content-Length") && !k.equalsIgnoreCase("Transfer-Encoding") && !k.equalsIgnoreCase("Pragma") && !k.equalsIgnoreCase("Expires") && !k.equalsIgnoreCase("Cache-Control")) {
                        savedHeaders.put(k, new ArrayList<>(entry.getValue()));
                    }
                }
                staticCache.put(path, new CachedItem(code, data, savedHeaders));
                respHeaders.set("Cache-Control", "public, max-age=31536000, immutable");
                respHeaders.remove("Pragma");
                respHeaders.remove("Expires");
            }

            exchange.sendResponseHeaders(code, data.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(data);
            }

        } catch (Exception e) {
            String err = "iLO Bridge Fehler: " + e.getMessage();
            byte[] errBytes = err.getBytes();
            exchange.sendResponseHeaders(502, errBytes.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(errBytes);
            }
        }
    }

    public static void initSsl() throws Exception {
        System.setProperty("jdk.tls.client.disableExtensions", "true");
        System.setProperty("sun.security.ssl.allowUnsafeRenegotiation", "true");
        System.setProperty("https.protocols", "TLSv1,TLSv1.1,TLSv1.2");
        System.setProperty("http.keepAlive", "true");
        System.setProperty("http.maxConnections", "30");
        System.setProperty("sun.net.http.errorstream.enableBuffering", "true");

        TrustManager[] trustAll = new TrustManager[]{
            new X509TrustManager() {
                public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
                public void checkClientTrusted(X509Certificate[] c, String a) {}
                public void checkServerTrusted(X509Certificate[] c, String a) {}
            }
        };

        SSLContext sc = SSLContext.getInstance("TLSv1");
        sc.init(null, trustAll, new java.security.SecureRandom());
        sslSocketFactory = new CustomSSLSocketFactory(sc.getSocketFactory());
    }

    public static SSLSocketFactory getSslSocketFactory() {
        if (sslSocketFactory == null) {
            try {
                initSsl();
            } catch (Exception e) {
                System.err.println("[TlsBridge] Error initializing legacy SSL: " + e.getMessage());
            }
        }
        return sslSocketFactory;
    }

    public static class CustomSSLSocketFactory extends SSLSocketFactory {
        private final SSLSocketFactory delegate;
        public CustomSSLSocketFactory(SSLSocketFactory delegate) { this.delegate = delegate; }
        public String[] getDefaultCipherSuites() { return delegate.getSupportedCipherSuites(); }
        public String[] getSupportedCipherSuites() { return delegate.getSupportedCipherSuites(); }

        private Socket configure(Socket s) {
            if (s instanceof SSLSocket) {
                SSLSocket ssl = (SSLSocket) s;
                ssl.setEnabledProtocols(new String[]{"TLSv1", "TLSv1.1", "TLSv1.2"});
                ssl.setEnabledCipherSuites(ssl.getSupportedCipherSuites());
            }
            return s;
        }

        public Socket createSocket(Socket s, String h, int p, boolean a) throws IOException { return configure(delegate.createSocket(s, h, p, a)); }
        public Socket createSocket(String h, int p) throws IOException { return configure(delegate.createSocket(h, p)); }
        public Socket createSocket(String h, int p, InetAddress l, int lp) throws IOException { return configure(delegate.createSocket(h, p, l, lp)); }
        public Socket createSocket(InetAddress h, int p) throws IOException { return configure(delegate.createSocket(h, p)); }
        public Socket createSocket(InetAddress h, int p, InetAddress l, int lp) throws IOException { return configure(delegate.createSocket(h, p, l, lp)); }
    }
}
