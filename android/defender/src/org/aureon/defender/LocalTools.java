package org.aureon.defender;
import android.content.*;
import android.database.Cursor;
import android.provider.DocumentsContract;
import android.net.Uri;
import android.graphics.*;
import android.media.ExifInterface;
import java.io.*;
import java.util.*;

/** User-granted folder hashing and selected-image copies; no broad-storage privilege or deletion. */
public final class LocalTools {
    private LocalTools() {}
    public static String folder(Context c,Uri tree,Set<String> hashes) throws Exception {
        ArrayDeque<String> queue=new ArrayDeque<>();HashSet<String> seen=new HashSet<>();queue.add(DocumentsContract.getTreeDocumentId(tree));
        int scanned=0,errors=0,matches=0,folders=0;StringBuilder hits=new StringBuilder();
        while(!queue.isEmpty()&&scanned<2000&&folders<2000){String id=queue.removeFirst();if(!seen.add(id))continue;folders++;
            Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(tree,id);
            try(Cursor cur=c.getContentResolver().query(children,new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE},null,null,null)){
                if(cur==null){errors++;continue;}
                while(cur.moveToNext()&&scanned<2000){String child=cur.getString(0),name=cur.getString(1),mime=cur.getString(2);
                    if(DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)){if(queue.size()<2000)queue.add(child);else errors++;continue;}
                    scanned++;try(InputStream in=c.getContentResolver().openInputStream(DocumentsContract.buildDocumentUriUsingTree(tree,child))){String hash=FileChecks.hash(in,256L*1024*1024);if(hashes.contains(hash)){matches++;if(hits.length()<16000)hits.append("\nMATCH: ").append(name).append("\n").append(hash).append("\nReview before opening; delete only through your file manager after verification.\n");}}
                    catch(Exception ex){errors++;}
                }
            }catch(Exception ex){errors++;}
        }
        return "Selected-folder hash scan complete.\n"+scanned+" checked; "+matches+" imported-list matches; "+errors+" unreadable/oversized entries.\nLimit: 2,000 files / 2,000 folders / 256 MiB per file. "+((!queue.isEmpty()||scanned>=2000||folders>=2000)?"Limit reached; folder may be incomplete.":"")+"\nOnly the folder Android granted is accessible. No hash match does not establish safety. No files changed.\n"+hits;
    }
    public static String cleanImage(Context c,Uri source,Uri destination) throws Exception {
        if(source.equals(destination))throw new IOException("Choose a new output file; original must be preserved");
        BitmapFactory.Options bounds=new BitmapFactory.Options();bounds.inJustDecodeBounds=true;
        try(InputStream in=c.getContentResolver().openInputStream(source)){BitmapFactory.decodeStream(in,null,bounds);}
        if(bounds.outWidth<=0||bounds.outHeight<=0||((long)bounds.outWidth*bounds.outHeight)>24000000)throw new IOException("Invalid image or exceeds 24 megapixel cleanup limit");
        if(!"image/jpeg".equals(bounds.outMimeType)&&!"image/png".equals(bounds.outMimeType))throw new IOException("Choose JPEG or PNG. Other formats are not supported here.");
        int orientation=1;
        try(InputStream in=c.getContentResolver().openInputStream(source)){orientation=new ExifInterface(in).getAttributeInt(ExifInterface.TAG_ORIENTATION,1);}
        Bitmap bitmap;
        try(InputStream in=c.getContentResolver().openInputStream(source)){bitmap=BitmapFactory.decodeStream(in);}
        if(bitmap==null)throw new IOException("Cannot decode image");
        Matrix m=new Matrix();
        switch(orientation){case 2:m.setScale(-1,1);break;case 3:m.setRotate(180);break;case 4:m.setScale(1,-1);break;case 5:m.setRotate(90);m.postScale(-1,1);break;case 6:m.setRotate(90);break;case 7:m.setRotate(270);m.postScale(-1,1);break;case 8:m.setRotate(270);break;}
        Bitmap rotated=orientation==1?bitmap:Bitmap.createBitmap(bitmap,0,0,bitmap.getWidth(),bitmap.getHeight(),m,true);
        try(OutputStream out=c.getContentResolver().openOutputStream(destination,"w")){if(out==null||!rotated.compress(Bitmap.CompressFormat.PNG,100,out))throw new IOException("Could not write clean PNG copy");}
        finally{if(rotated!=bitmap)rotated.recycle();bitmap.recycle();}
        return "Created a PNG copy from decoded image pixels, without copying source EXIF/XMP/comments. Original retained. Orientation applied. Visible content, watermarks, steganography, external file records and all fingerprints are NOT removed. Review the output before sharing. PNG may be larger; animated/multi-frame formats are unsupported.";
    }
}
