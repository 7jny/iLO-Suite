package com.hp.ilo2.intgapp;

import util.Http;
import util.TlsBridge;

import javax.net.ssl.HttpsURLConnection;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class jsonparser {
    private final intgapp ParentApp;

    public jsonparser(intgapp intgappVar) {
        this.ParentApp = intgappVar;
    }

    public String postJSONRequest(String str, String str2) {
        String host = this.ParentApp.getCodeBase().getHost();
        int port = this.ParentApp.getCodeBase().getPort();
        String portStr = (port >= 0) ? (":" + port) : "";
        String parameter = this.ParentApp.getParameter("RCINFO1");
        byte[] payload = (str2 != null) ? str2.getBytes(StandardCharsets.UTF_8) : new byte[0];

        System.out.println("[jsonparser] Making JSON POST Request: " + str + ", data: " + str2);

        // 1. Direct HTTPS attempt with custom SSL socket factory (3DES / TLS 1.0)
        try {
            String directUrlStr = "https://" + host + portStr + "/json/" + str;
            URL directUrl = new URL(directUrlStr);
            HttpsURLConnection conn = (HttpsURLConnection) directUrl.openConnection();
            conn.setRequestMethod("POST");
            conn.setDoInput(true);
            conn.setDoOutput(true);
            conn.setUseCaches(false);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(12000);
            conn.setSSLSocketFactory(TlsBridge.getSslSocketFactory());
            conn.setHostnameVerifier((h, s) -> true);
            if (parameter != null && !parameter.isEmpty()) {
                conn.setRequestProperty("Cookie", "sessionKey=" + parameter);
            }
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Content-Length", String.valueOf(payload.length));
            try (OutputStream os = conn.getOutputStream()) {
                os.write(payload);
                os.flush();
            }
            int responseCode = conn.getResponseCode();
            InputStream is = (responseCode >= 200 && responseCode < 400) ? conn.getInputStream() : conn.getErrorStream();
            if (is != null) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line).append('\n');
                    }
                    String respStr = sb.toString();
                    if (responseCode == 200) return "Success";
                    if (respStr.contains("SCSI_ERR_NO_LICENSE")) return "SCSI_ERR_NO_LICENSE";
                    return respStr;
                }
            }
        } catch (Exception e) {
            System.out.println("[jsonparser] Direct POST /json/" + str + " notice: " + e.getMessage() + ", trying bridge fallback...");
        }

        // 2. Fallback via local TLS Bridge on port 8089
        try {
            String bridgeUrlStr = "http://127.0.0.1:8089/json/" + str;
            URL bridgeUrl = new URL(bridgeUrlStr);
            HttpURLConnection conn = (HttpURLConnection) bridgeUrl.openConnection();
            conn.setRequestMethod("POST");
            conn.setDoInput(true);
            conn.setDoOutput(true);
            conn.setUseCaches(false);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(12000);
            if (parameter != null && !parameter.isEmpty()) {
                conn.setRequestProperty("Cookie", "sessionKey=" + parameter);
            }
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Content-Length", String.valueOf(payload.length));
            try (OutputStream os = conn.getOutputStream()) {
                os.write(payload);
                os.flush();
            }
            int responseCode = conn.getResponseCode();
            InputStream is = (responseCode >= 200 && responseCode < 400) ? conn.getInputStream() : conn.getErrorStream();
            if (is != null) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line).append('\n');
                    }
                    String respStr = sb.toString();
                    if (responseCode == 200) return "Success";
                    if (respStr.contains("SCSI_ERR_NO_LICENSE")) return "SCSI_ERR_NO_LICENSE";
                    return respStr;
                }
            }
        } catch (Exception e) {
            System.err.println("[jsonparser] Bridge POST /json/" + str + " notice: " + e.getMessage());
        }

        this.ParentApp.rcErrMessage = "POST-Anfrage an iLO fehlgeschlagen (/json/" + str + ").";
        return null;
    }

    public String getJSONRequest(String str) {
        String host = this.ParentApp.getCodeBase().getHost();
        int port = this.ParentApp.getCodeBase().getPort();
        String portStr = (port >= 0) ? (":" + port) : "";
        String parameter = this.ParentApp.getParameter("RCINFO1");

        System.out.println("[jsonparser] Fetching GET /json/" + str + " from " + host + " (sessionKey=" + (parameter != null && !parameter.isEmpty() ? "set" : "none") + ")...");

        // 1. Direct HTTPS attempt with custom SSL socket factory (3DES / TLS 1.0)
        try {
            String directUrlStr = "https://" + host + portStr + "/json/" + str;
            URL directUrl = new URL(directUrlStr);
            HttpsURLConnection conn = (HttpsURLConnection) directUrl.openConnection();
            conn.setRequestMethod("GET");
            conn.setDoInput(true);
            conn.setDoOutput(false);
            conn.setUseCaches(false);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(12000);
            conn.setSSLSocketFactory(TlsBridge.getSslSocketFactory());
            conn.setHostnameVerifier((hostname, session) -> true);
            if (parameter != null && !parameter.isEmpty()) {
                conn.setRequestProperty("Cookie", "sessionKey=" + parameter);
            }
            conn.connect();
            int respCode = conn.getResponseCode();
            if (respCode == 200) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line).append('\n');
                    }
                    String res = sb.toString();
                    System.out.println("[jsonparser] Direct GET /json/" + str + " success: " + res.trim());
                    return res;
                }
            } else {
                System.out.println("[jsonparser] Direct GET /json/" + str + " returned HTTP " + respCode);
            }
        } catch (Exception e) {
            System.out.println("[jsonparser] Direct GET /json/" + str + " notice: " + e.getMessage() + ", trying bridge fallback...");
        }

        // 2. Fallback via local TLS Bridge on port 8089 (running inside Python backend)
        try {
            String bridgeUrlStr = "http://127.0.0.1:8089/json/" + str;
            URL bridgeUrl = new URL(bridgeUrlStr);
            HttpURLConnection conn = (HttpURLConnection) bridgeUrl.openConnection();
            conn.setRequestMethod("GET");
            conn.setDoInput(true);
            conn.setDoOutput(false);
            conn.setUseCaches(false);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(12000);
            if (parameter != null && !parameter.isEmpty()) {
                conn.setRequestProperty("Cookie", "sessionKey=" + parameter);
            }
            conn.connect();
            int respCode = conn.getResponseCode();
            if (respCode == 200) {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line).append('\n');
                    }
                    String res = sb.toString();
                    System.out.println("[jsonparser] Bridge GET /json/" + str + " success: " + res.trim());
                    return res;
                }
            } else {
                System.out.println("[jsonparser] Bridge GET /json/" + str + " returned HTTP " + respCode);
            }
        } catch (Exception e) {
            System.err.println("[jsonparser] Bridge GET /json/" + str + " notice: " + e.getMessage());
        }

        this.ParentApp.rcErrMessage = "Parameter konnten nicht von iLO abgerufen werden (/json/" + str + ").";
        return null;
    }

    public String getJSONObject(String str, String str2) {
        if (str == null || str.trim().isEmpty()) return "{}";
        String trim = str.trim();
        int end = trim.indexOf("}");
        if (end < 0) return "{}";
        String substring = trim.substring(1, end + 1);
        int start = substring.indexOf("{");
        if (start < 0) return "{}";
        return substring.substring(start);
    }

    public int getJSONNumber(String str, String str2) {
        if (str == null || str.trim().isEmpty()) return 0;
        String trim = str.trim();
        if (!trim.startsWith("{") || !trim.endsWith("}")) return 0;
        for (String str3 : trim.substring(1, trim.length() - 1).split(",")) {
            String[] split = str3.split(":");
            if (split.length < 2) continue;
            String trim2 = split[0].trim().replace("\"", "");
            if (trim2.compareToIgnoreCase(str2) == 0) {
                try {
                    return Integer.parseInt(split[1].trim().replace("\"", ""));
                } catch (NumberFormatException ignored) {}
            }
        }
        return 0;
    }

    public String getJSONArray(String str, String str2, int i) {
        if (str == null || str.trim().isEmpty()) return "{}";
        String trim = str.trim();
        int bStart = trim.indexOf("[");
        int bEnd = trim.indexOf("]");
        if (bStart < 0 || bEnd < 0 || bStart >= bEnd) return "{}";
        String substring = trim.substring(bStart + 1);
        String substring2 = substring.substring(0, substring.indexOf("]") + 1);
        String[] parts = substring2.substring(1, substring2.length() - 1).split("},\\{");
        if (i >= 0 && i < parts.length) {
            return "{" + parts[i] + "}";
        }
        return "{}";
    }
}
