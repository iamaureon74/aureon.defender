import org.aureon.defender.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Native fold-memory on a desktop JVM: dedupe, versions, verified restore, refusal, cap, ransomware undo. */
public class MemoryTest {
 static void check(boolean ok,String what){if(!ok)throw new AssertionError(what);}
 static File write(File f,byte[] b)throws IOException{f.getParentFile().mkdirs();Files.write(f.toPath(),b);return f;}
 public static void main(String[] a)throws Exception{
  File tmp=Files.createTempDirectory("aureon-mem").toFile(),docs=new File(tmp,"Documents"),store=new File(tmp,"store");
  Random rnd=new Random(7);int n=0;
  StringBuilder text=new StringBuilder();for(int i=0;i<4000;i++)text.append("line ").append(i%37).append(" of the quarterly plan\n");
  byte[] plain=text.toString().getBytes("UTF-8");
  for(int i=0;i<6;i++)write(new File(docs,"doc"+i+".txt"),(new String(plain,"UTF-8")+"doc "+i).getBytes("UTF-8"));
  write(new File(docs,"copy.txt"),Files.readAllBytes(new File(docs,"doc0.txt").toPath()));
  long t0=1_000_000;
  Memory.Result r=Memory.run(store,Collections.singletonList(docs),5000,1L<<30,Long.MAX_VALUE,t0);
  check(r.folded==7&&r.held==7,"first pass folds every file");n++;
  long disk=r.disk;check(disk<plain.length*3,"near-identical documents share bites ("+disk+" bytes for 7 x "+plain.length+")");n++;
  r=Memory.run(store,Collections.singletonList(docs),5000,1L<<30,Long.MAX_VALUE,t0+1);
  check(r.folded==0,"unchanged files cost nothing");n++;
  File d0=new File(docs,"doc0.txt");byte[] v1=Files.readAllBytes(d0.toPath());
  write(d0,(new String(v1,"UTF-8")+"\nedited").getBytes("UTF-8"));d0.setLastModified(d0.lastModified()+5000);
  r=Memory.run(store,Collections.singletonList(docs),5000,1L<<30,Long.MAX_VALUE,t0+2);
  check(r.folded==1&&r.versions==1,"an edit adds one version");n++;
  MemoryStore m=new MemoryStore(store);List<MemoryStore.Version> vs=m.versions(d0.getAbsolutePath());
  File back=new File(tmp,"back.txt");m.restore(vs.get(1).sha,back);
  check(Arrays.equals(Files.readAllBytes(back.toPath()),v1),"earlier version comes back exactly");n++;
  File[] bites=new File(store,"chunks").listFiles()[0].listFiles();
  try(RandomAccessFile f=new RandomAccessFile(bites[0],"rw")){f.seek(f.length()/2);int x=f.read();f.seek(f.length()/2);f.write(x^0xff);}
  boolean refused=false;
  for(String p:m.paths())for(MemoryStore.Version v:m.versions(p)){try{m.restore(v.sha,new File(tmp,"x"));}catch(IOException e){refused|=e.getMessage().startsWith("refused");}}
  check(refused,"a damaged bite is refused, not handed back");n++;
  check(!new File(tmp,".x.aureon-restore").exists(),"nothing half-written is left");n++;
  // fresh store for the attack (the damaged bite above would make one restore refuse)
  File store2=new File(tmp,"store2");Memory.run(store2,Collections.singletonList(docs),5000,1L<<30,Long.MAX_VALUE,t0);
  Map<String,byte[]> before=new HashMap<>();for(File f:docs.listFiles())before.put(f.getName(),Files.readAllBytes(f.toPath()));
  for(int i=1;i<=4;i++){File f=new File(docs,"doc"+i+".txt");byte[] junk=new byte[30000];rnd.nextBytes(junk);write(f,junk);f.setLastModified(f.lastModified()+9000);}
  File d5=new File(docs,"doc5.txt");d5.delete();byte[] junk=new byte[30000];rnd.nextBytes(junk);write(new File(docs,"doc5.txt.locked"),junk);
  r=Memory.run(store2,Collections.singletonList(docs),5000,1L<<30,Long.MAX_VALUE,t0+3);
  check(r.restored.size()==5,"five encrypted files are put back: "+r.restored);n++;
  for(int i=1;i<=5;i++)check(Arrays.equals(Files.readAllBytes(new File(docs,"doc"+i+".txt").toPath()),before.get("doc"+i+".txt")),"doc"+i+" restored exactly");n++;
  check(!new File(docs,"doc5.txt.locked").exists(),"encrypted twin deleted");n++;
  // one encrypted-looking file alone is not an attack: folded as a normal change
  File solo=new File(docs,"copy.txt");byte[] z=new byte[30000];rnd.nextBytes(z);write(solo,z);solo.setLastModified(solo.lastModified()+9000);
  r=Memory.run(store2,Collections.singletonList(docs),5000,1L<<30,Long.MAX_VALUE,t0+4);
  check(r.restored.isEmpty()&&r.folded==1,"a single dense change is a normal edit");n++;
  r=Memory.run(store2,Collections.singletonList(docs),5000,1L<<30,1,t0+5);
  check(r.versions<=2,"cap trims old versions ("+r.versions+")");n++;
  check(MemoryStore.entropy(junk)>7.9&&MemoryStore.entropy(plain)<5,"entropy scale");n++;
  System.out.println(n+" Android memory assertions passed");
 }
}
