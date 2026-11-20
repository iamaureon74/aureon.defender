import org.aureon.defender.Rules;
public class RulesTest {
 public static void main(String[] args) throws Exception {
  if(!Rules.classify(false,false,false,false).isEmpty())throw new AssertionError("No grants should produce no permission review");
  if(!Rules.classify(true,true,true,false).contains("Review"))throw new AssertionError("Sensitive grants must be reviewed");
  if(!Rules.classify(false,true,false,true).contains("SMS"))throw new AssertionError("SMS/mic review missing");
  if(!Rules.classify(true,false,false,false).isEmpty())throw new AssertionError("Camera grant alone is not malware");
  if(!Rules.scope().contains("not malware"))throw new AssertionError("Scope must preserve uncertainty");
  String expected="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
  if(!org.aureon.defender.FileChecks.hash(new java.io.ByteArrayInputStream("abc".getBytes("UTF-8")),3).equals(expected))throw new AssertionError("SHA-256 known-answer mismatch");
  if(!org.aureon.defender.FileChecks.blocklist(new java.io.ByteArrayInputStream(("# local test\n"+expected+"\n").getBytes("UTF-8"))).contains(expected))throw new AssertionError("Blocklist parse failure");
  try{org.aureon.defender.FileChecks.hash(new java.io.ByteArrayInputStream(new byte[4]),3);throw new AssertionError("Size bound ignored");}catch(java.io.IOException ok){}
  try{org.aureon.defender.FileChecks.blocklist(new java.io.ByteArrayInputStream("not-a-hash".getBytes("UTF-8")));throw new AssertionError("Invalid hash accepted");}catch(java.io.IOException ok){}
  try{org.aureon.defender.FileChecks.blocklist(new java.io.ByteArrayInputStream(new byte[1024*1024+1]));throw new AssertionError("Oversized import accepted");}catch(java.io.IOException ok){}
  if(!Rules.listener("com.google.android.as").contains("on-device AI"))throw new AssertionError("Ambient AI listener missing");
  if(!Rules.listener("com.example.notes").isEmpty())throw new AssertionError("Ordinary app flagged as listener");
  java.util.Set<String> none=java.util.Collections.emptySet();java.util.List<String> noZip=java.util.Collections.emptyList();
  if(!org.aureon.defender.ShieldRules.verdict("holiday.jpg.apk",new byte[]{'P','K',3,4},noZip,null,none).contains("double extension"))throw new AssertionError("Double extension missed");
  if(!org.aureon.defender.ShieldRules.verdict("statement.pdf",new byte[]{'P','K',3,4},java.util.Arrays.asList("AndroidManifest.xml","classes.dex"),null,none).contains("Android app disguised"))throw new AssertionError("Disguised APK missed");
  if(!org.aureon.defender.ShieldRules.verdict("update.apk",new byte[]{'P','K',3,4},java.util.Arrays.asList("AndroidManifest.xml","classes.dex"),null,none).isEmpty())throw new AssertionError("A real APK named .apk is not disguised");
  if(!org.aureon.defender.ShieldRules.verdict("scan.png",new byte[]{0x7f,'E','L','F'},noZip,null,none).contains("program disguised"))throw new AssertionError("ELF in image missed");
  if(!org.aureon.defender.ShieldRules.verdict("notes.txt","hello".getBytes("UTF-8"),noZip,null,none).isEmpty())throw new AssertionError("Plain text flagged");
  if(!org.aureon.defender.ShieldRules.verdict("a.bin",new byte[0],noZip,expected,java.util.Collections.singleton(expected)).contains("blocklist"))throw new AssertionError("Blocklist hash missed");
  if(!org.aureon.defender.ShieldRules.hardwareNeeds("Android/obb/game/main.obb")||!org.aureon.defender.ShieldRules.hardwareNeeds(".thumbnails/x")||org.aureon.defender.ShieldRules.hardwareNeeds("Download/x.pdf"))throw new AssertionError("Hardware-needed folders wrong");
  int[] small=org.aureon.defender.ShieldRules.budget(4,3,80,false,0,false),big=org.aureon.defender.ShieldRules.budget(8,12,80,false,0,false),hot=org.aureon.defender.ShieldRules.budget(8,12,80,false,4,false);
  if(small[0]!=0||big[0]!=2||big[1]<=small[1])throw new AssertionError("Budget does not scale with hardware");
  if(hot[3]!=1||hot[1]>=big[1])throw new AssertionError("Hot phone should do a quick pass");
  System.out.println("22 Android rule/file-check assertions passed");
 }
}
