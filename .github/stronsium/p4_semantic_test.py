import unittest
import p4_semantic as S
def ctx(path,head,diff,status='modified',findings=None):
 return {'paths':[{'filename':path,'status':status}],'sources':{path:head},'diff':diff,'finding_ids':findings or []}
def d(p,body):return "diff --git a/%s b/%s\nindex 1..2 100644\n--- a/%s\n+++ b/%s\n%s"%(p,p,p,p,body)
HEAD="import os\n\n# explain\ndef f(x):\n    return x + 1\n"
class T(unittest.TestCase):
 def test_comment_only_passes(self):
  diff=d('a.py',"@@ -1,4 +1,5 @@\n import os\n \n+# explain\n def f(x):\n     return x + 1\n")
  # base = head without the '# explain' line
  r=S.classify_semantic(ctx('a.py',HEAD,diff));self.assertTrue(r['scope']['ast_equivalent_only'])
 def test_whitespace_format_passes(self):
  head="x = [1, 2]\n"
  diff=d('a.py',"@@ -1 +1 @@\n-x=[1,2]\n+x = [1, 2]\n")
  self.assertEqual(S.classify_semantic(ctx('a.py',head,diff))['findings'],[])
 def test_behavior_change_rejected(self):
  head="def f(x):\n    return x + 2\n"
  diff=d('a.py',"@@ -1,2 +1,2 @@\n def f(x):\n-    return x + 1\n+    return x + 2\n")
  with self.assertRaisesRegex(ValueError,'p4_sem_ast_changed'):S.classify_semantic(ctx('a.py',head,diff))
 def test_string_and_docstring_change_rejected(self):
  head='def f():\n    """new"""\n'
  diff=d('a.py','@@ -1,2 +1,2 @@\n def f():\n-    """old"""\n+    """new"""\n')
  with self.assertRaisesRegex(ValueError,'p4_sem_ast_changed'):S.classify_semantic(ctx('a.py',head,diff))
 def test_non_python_and_status_rejected(self):
  with self.assertRaisesRegex(ValueError,'p4_sem_not_python'):S.classify_semantic(ctx('docs/a.md','x\n',d('docs/a.md',"@@ -1 +1 @@\n-y\n+x\n")))
  with self.assertRaisesRegex(ValueError,'p4_sem_status'):S.classify_semantic(ctx('a.py','x=1\n',d('a.py',"@@ -0,0 +1 @@\n+x=1\n"),status='added'))
 def test_diff_must_match_source(self):
  diff=d('a.py',"@@ -1 +1 @@\n-x=[1,2]\n+y = [1, 2]\n")
  with self.assertRaisesRegex(ValueError,'p4_sem_diff_does_not_match_source'):S.classify_semantic(ctx('a.py',"x = [1, 2]\n",diff))
 def test_encoding_cookie_change_rejected(self):
  head="# -*- coding: latin-1 -*-\nx = 1\n"
  diff=d('a.py',"@@ -1,2 +1,2 @@\n-# -*- coding: utf-8 -*-\n+# -*- coding: latin-1 -*-\n x = 1\n")
  with self.assertRaisesRegex(ValueError,'p4_sem_(header_lines|directive_comment)_changed'):S.classify_semantic(ctx('a.py',head,diff))
 def test_structural_and_findings_and_mismatch(self):
  for bad in ("\nrename from a.py\n","\nnew mode 100755\n","\nGIT binary patch\n"):
   diff=d('a.py',"@@ -1 +1 @@\n-#a\n+#b\n").replace("index 1..2 100644","index 1..2 100644"+bad.rstrip("\n"))
   with self.assertRaises(ValueError):S.classify_semantic(ctx('a.py',"#b\n",diff))
  with self.assertRaisesRegex(ValueError,'open_findings'):S.classify_semantic(ctx('a.py',"#b\n",d('a.py',"@@ -1 +1 @@\n-#a\n+#b\n"),findings=['review:1']))
  c=ctx('a.py',"#b\n",d('b.py',"@@ -1 +1 @@\n-#a\n+#b\n"))
  with self.assertRaises(ValueError):S.classify_semantic(c)
 def test_unparseable_rejected(self):
  with self.assertRaisesRegex(ValueError,'p4_sem_unparseable'):S.classify_semantic(ctx('a.py',"def (:\n",d('a.py',"@@ -1 +1 @@\n-#a\n+def (:\n")))
 def test_multi_hunk_and_crlf(self):
  head="a = 1\n# c1\nb = 2\nc = 3\n# c2\n"
  diff=d('a.py',"@@ -1,2 +1,3 @@\n a = 1\n+# c1\n b = 2\n@@ -3,1 +4,2 @@\n c = 3\n+# c2\n")
  self.assertTrue(S.classify_semantic(ctx('a.py',head,diff)))
  self.assertTrue(S.classify_semantic(ctx('a.py',head.replace('\n','\r\n'),diff)))

 def test_source_sensitive_and_directive_changes_rejected(self):
  head="import inspect\n# c\nx = 1\n"
  with self.assertRaisesRegex(ValueError,'p4_sem_source_sensitive'):S.classify_semantic(ctx('a.py',head,d('a.py',"@@ -1,2 +1,3 @@\n import inspect\n+# c\n x = 1\n")))
  head2="x = 1  # noqa: E501\n"
  with self.assertRaisesRegex(ValueError,'p4_sem_directive_comment_changed'):S.classify_semantic(ctx('a.py',head2,d('a.py',"@@ -1 +1 @@\n-x = 1\n+x = 1  # noqa: E501\n")))
  head3="x = 1  # type: ignore\n"
  with self.assertRaisesRegex(ValueError,'p4_sem_directive_comment_changed'):S.classify_semantic(ctx('a.py',head3,d('a.py',"@@ -1 +1 @@\n-x = 1  # type: ignore[x]\n+x = 1  # type: ignore\n")))
 def test_observational_scope_not_accepted_by_default(self):
  self.assertIs(S.OBSERVATIONAL_SCOPE_OWNER_ACCEPTED,False)
  self.assertIn('NOT verified',S.classify_semantic(ctx('a.py',"# a\nx = 1\n",d('a.py',"@@ -1 +1,2 @@\n+# a\n x = 1\n")))['scope']['reasons'][0])
if __name__=='__main__':unittest.main()
