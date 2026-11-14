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
  System.out.println("10 Android rule/file-check assertions passed");
 }
}
