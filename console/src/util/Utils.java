package util;

import java.awt.Image;
import java.awt.Toolkit;
import java.awt.image.BufferedImage;
import java.net.URL;
import javax.swing.JApplet;

public class Utils {
    private static final BufferedImage EMPTY_IMAGE = new BufferedImage(16, 16, BufferedImage.TYPE_INT_ARGB);

    public static Image getResourceImage(JApplet applet, String image) {
        try {
            if (applet != null) {
                URL resource = applet.getClass().getClassLoader().getResource(image);
                if (resource != null) {
                    return Toolkit.getDefaultToolkit().getImage(resource);
                }
            }
            URL globalResource = Utils.class.getClassLoader().getResource(image);
            if (globalResource != null) {
                return Toolkit.getDefaultToolkit().getImage(globalResource);
            }
        } catch (Exception ignored) {}
        return EMPTY_IMAGE;
    }
}
