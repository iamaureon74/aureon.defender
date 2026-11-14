package org.aureon.defender.tests;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.*;
public class Fixtures extends ContentProvider {
 public boolean onCreate(){return true;}
 public String getType(Uri u){return "application/octet-stream";}
 public Cursor query(Uri u,String[] p,String s,String[] a,String order){return null;}
 public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
 public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
 public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
 public ParcelFileDescriptor openFile(Uri u,String mode) throws FileNotFoundException {
  String name=u.getLastPathSegment();String content;
  if("export".equals(name))return ParcelFileDescriptor.open(new File(getContext().getCacheDir(),"export"),mode.contains("w")?ParcelFileDescriptor.MODE_CREATE|ParcelFileDescriptor.MODE_TRUNCATE|ParcelFileDescriptor.MODE_READ_WRITE:ParcelFileDescriptor.MODE_READ_ONLY);
  if("abc".equals(name))content="abc";
  else if("hashes".equals(name))content="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\n";
  else if("invalid".equals(name))content="not-a-hash";
  else throw new FileNotFoundException();
  File f=new File(getContext().getCacheDir(),name);
  try(FileOutputStream out=new FileOutputStream(f)){out.write(content.getBytes("UTF-8"));}catch(IOException e){throw new FileNotFoundException(e.toString());}
  return ParcelFileDescriptor.open(f,ParcelFileDescriptor.MODE_READ_ONLY);
 }
}
