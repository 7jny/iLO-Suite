import com.hp.ilo2.intgapp.intgapp;
import util.Http;
import util.TlsBridge;

import javax.net.ssl.HttpsURLConnection;
import javax.swing.*;
import java.awt.*;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.regex.*;

public class Main {
    public static void main(String[] args) {
        // Configure SSL globally before anything else
        try {
            System.setProperty("jdk.tls.client.disableExtensions", "true");
            System.setProperty("sun.security.ssl.allowUnsafeRenegotiation", "true");
            System.setProperty("https.protocols", "TLSv1,TLSv1.1");
            TlsBridge.initSsl();
            HttpsURLConnection.setDefaultSSLSocketFactory(TlsBridge.getSslSocketFactory());
            HttpsURLConnection.setDefaultHostnameVerifier((h, s) -> true);
        } catch (Exception e) {
            System.err.println("[Main] Warning during SSL init: " + e.getMessage());
        }

        // Set Look and Feel to native System Look and Feel
        try {
            UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
        } catch (Exception ignored) {}

        String host = "";
        String user = "";
        String pass = "";
        String sessionKey = "";

        // Parse arguments
        for (int i = 0; i < args.length; i++) {
            if (args[i].equalsIgnoreCase("--session-key") && i + 1 < args.length) {
                sessionKey = args[i + 1].trim();
                i++;
            } else if (host.isEmpty()) {
                host = args[i].trim();
            } else if (user.isEmpty()) {
                user = args[i].trim();
            } else if (pass.isEmpty()) {
                pass = args[i].trim();
            }
        }

        if (host.isEmpty() || (sessionKey.isEmpty() && (user.isEmpty() || pass.isEmpty()))) {
            // Show interactive GUI connection dialog
            String[] creds = showLoginDialog();
            if (creds == null) {
                System.out.println("Verbindung durch Benutzer abgebrochen.");
                System.exit(0);
            }
            host = creds[0];
            user = creds[1];
            pass = creds[2];
        }

        try {
            if (sessionKey.isEmpty()) {
                System.out.println("[iLO 3 Console] Authenticating to " + host + " as " + user + "...");
                sessionKey = performLogin(host, user, pass);
                System.out.println("[iLO 3 Console] Authentication successful. Session key acquired.");
            } else {
                System.out.println("[iLO 3 Console] Reusing existing authenticated session key.");
            }

            Http.setSessionKey(sessionKey);

            System.out.println("[iLO 3 Console] Initializing remote console applet for " + host + "...");
            final String targetHost = host;
            SwingUtilities.invokeLater(() -> {
                try {
                    intgapp app = new intgapp(targetHost);
                    app.init();
                    app.start();
                    System.out.println("[iLO 3 Console] Remote console started successfully.");
                } catch (Throwable t) {
                    t.printStackTrace();
                    JOptionPane.showMessageDialog(
                        null,
                        "Fehler beim Starten der Konsole:\n" + t.getMessage(),
                        "iLO 3 Konsole - Fehler",
                        JOptionPane.ERROR_MESSAGE
                    );
                }
            });

        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(
                null,
                "Verbindung zu iLO 3 fehlgeschlagen:\n" + e.getMessage(),
                "iLO 3 Verbindung - Fehler",
                JOptionPane.ERROR_MESSAGE
            );
            System.exit(1);
        }
    }

    private static String[] showLoginDialog() {
        JPanel panel = new JPanel(new GridLayout(3, 2, 8, 8));
        panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));

        JTextField hostField = new JTextField("192.168.1.134");
        JTextField userField = new JTextField("Administrator");
        JPasswordField passField = new JPasswordField();

        panel.add(new JLabel("iLO 3 Host / IP:"));
        panel.add(hostField);
        panel.add(new JLabel("Benutzername:"));
        panel.add(userField);
        panel.add(new JLabel("Passwort:"));
        panel.add(passField);

        int result = JOptionPane.showConfirmDialog(
            null,
            panel,
            "HP iLO 3 Standalone Konsole (Windows 11)",
            JOptionPane.OK_CANCEL_OPTION,
            JOptionPane.PLAIN_MESSAGE
        );

        if (result == JOptionPane.OK_OPTION) {
            String host = hostField.getText().trim();
            String user = userField.getText().trim();
            String pass = new String(passField.getPassword()).trim();
            if (!host.isEmpty() && !user.isEmpty()) {
                return new String[]{host, user, pass};
            }
        }
        return null;
    }

    private static String performLogin(String host, String user, String pass) throws Exception {
        if (host.startsWith("http://")) host = host.substring(7);
        if (host.startsWith("https://")) host = host.substring(8);
        if (host.endsWith("/")) host = host.substring(0, host.length() - 1);

        String json = "{\"method\":\"login\",\"user_login\":\"" + escapeJson(user) + "\",\"password\":\"" + escapeJson(pass) + "\"}";
        byte[] bytes = json.getBytes("UTF-8");

        // 1. First attempt: Direct HTTPS with custom SSL socket factory (3DES / TLS 1.0)
        try {
            URL directUrl = new URL("https://" + host + "/json/login_session");
            HttpsURLConnection conn = (HttpsURLConnection) directUrl.openConnection();
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setUseCaches(false);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(15000);
            conn.setSSLSocketFactory(TlsBridge.getSslSocketFactory());
            conn.setHostnameVerifier((h, s) -> true);
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Content-Length", String.valueOf(bytes.length));

            try (OutputStream os = conn.getOutputStream()) {
                os.write(bytes);
                os.flush();
            }

            String resp = readResponse(conn);
            String key = extractSessionKey(resp);
            if (key != null) return key;
        } catch (Exception directErr) {
            System.out.println("[Main] Direct login attempt noticed: " + directErr.getMessage() + ", trying local bridge...");
        }

        // 2. Second attempt: Via running local TLS Bridge on port 8089
        try {
            URL bridgeUrl = new URL("http://127.0.0.1:8089/json/login_session");
            HttpURLConnection bridgeConn = (HttpURLConnection) bridgeUrl.openConnection();
            bridgeConn.setRequestMethod("POST");
            bridgeConn.setDoOutput(true);
            bridgeConn.setUseCaches(false);
            bridgeConn.setConnectTimeout(8000);
            bridgeConn.setReadTimeout(12000);
            bridgeConn.setRequestProperty("Content-Type", "application/json");
            bridgeConn.setRequestProperty("Content-Length", String.valueOf(bytes.length));

            try (OutputStream os = bridgeConn.getOutputStream()) {
                os.write(bytes);
                os.flush();
            }

            String resp = readResponse(bridgeConn);
            String key = extractSessionKey(resp);
            if (key != null) return key;
        } catch (Exception bridgeErr) {
            System.err.println("[Main] Bridge login error: " + bridgeErr.getMessage());
        }

        throw new RuntimeException("Anmeldung fehlgeschlagen. Bitte Zugangsdaten und Netzwerkverbindung pruefen.");
    }

    private static String readResponse(HttpURLConnection conn) throws IOException {
        int code = conn.getResponseCode();
        InputStream stream = (code >= 200 && code < 400) ? conn.getInputStream() : conn.getErrorStream();
        if (stream == null) throw new IOException("HTTP " + code + " von Server empfangen");

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, "UTF-8"))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) sb.append(line);
            return sb.toString();
        }
    }

    private static String extractSessionKey(String response) {
        Matcher m = Pattern.compile("\"session_key\"\\s*:\\s*\"([^\"]+)\"").matcher(response);
        if (m.find()) {
            return m.group(1);
        }
        Matcher errM = Pattern.compile("\"message\"\\s*:\\s*\"([^\"]+)\"").matcher(response);
        if (errM.find()) {
            throw new RuntimeException("iLO Fehler: " + errM.group(1));
        }
        return null;
    }

    private static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
