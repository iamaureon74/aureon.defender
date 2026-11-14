package org.aureon.defender;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
public final class FileChecks {
    private FileChecks() {}
    public static String hash(InputStream in,long max) throws Exception {
        if(in==null)throw new IOException("Cannot open selected file");
        MessageDigest md=MessageDigest.getInstance("SHA-256");long size=0;byte[] b=new byte[65536];int n;
        while((n=in.read(b))!=-1){size+=n;if(size>max)throw new IOException("File exceeds check limit");md.update(b,0,n);}
        StringBuilder result=new StringBuilder();for(byte item:md.digest())result.append(String.format(Locale.ROOT,"%02x",item&255));return result.toString();
    }
    public static Set<String> blocklist(InputStream in) throws IOException {
        if(in==null)throw new IOException("Cannot open blocklist");
        ByteArrayOutputStream buf=new ByteArrayOutputStream();byte[] chunk=new byte[8192];int n;
        while((n=in.read(chunk))!=-1){if(buf.size()+n>1024*1024)throw new IOException("Blocklist exceeds 1 MiB limit");buf.write(chunk,0,n);}
        Set<String> hashes=new HashSet<>();String[] lines=buf.toString("UTF-8").split("\\r?\\n");
        if(lines.length>10000)throw new IOException("Blocklist exceeds 10,000 lines");
        for(String line:lines){if(line.length()>256)throw new IOException("Blocklist line too long");line=line.trim().toLowerCase(Locale.ROOT);if(line.isEmpty()||line.startsWith("#"))continue;
            if(!line.matches("[0-9a-f]{64}"))throw new IOException("Expected one SHA-256 per line");hashes.add(line);}
        if(hashes.isEmpty())throw new IOException("Empty blocklist");return hashes;
    }
}
