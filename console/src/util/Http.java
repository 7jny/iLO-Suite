package util;

import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.util.Properties;
import javax.net.ssl.*;

public class Http {
    public static String sessionKey = "";
    public static SSLContext sslContext;
    public static SSLSocketFactory customSocketFactory;

    public static String getSessionKey() {
        return sessionKey;
    }

    public static void setSessionKey(String key) {
        sessionKey = key;
    }

    public static String getUrlHostname(String ip) {
        return "https://" + ip;
    }

    public static String getLoginUrl(String hostname) {
        return getUrlHostname(hostname) + "/json/login_session";
    }

    public static String getJavaAppletUrl(String hostname, String sessionKey) {
        return getUrlHostname(hostname) + "/html/java_irc.html?sessionKey=" + (sessionKey != null ? sessionKey : "");
    }

    static {
        try {
            TlsBridge.initSsl();
            customSocketFactory = TlsBridge.getSslSocketFactory();
            sslContext = SSLContext.getDefault();
            HttpsURLConnection.setDefaultSSLSocketFactory(customSocketFactory);
            HttpsURLConnection.setDefaultHostnameVerifier(new HostnameVerifier() {
                public boolean verify(String hostname, SSLSession session) {
                    return true;
                }
            });
        } catch (Exception e) {
            System.err.println("Warning: Error configuring Http SSL context: " + e.getMessage());
        }
    }
}
