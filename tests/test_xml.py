import unittest
import shutil
from xccdf_compose import *
from preup import xccdf
from preup import settings
import utils
try:
    from xml.etree.ElementTree import ParseError
except ImportError:
    from xml.parsers.expat import ExpatError as ParseError

from utils.xml_utils import XmlUtils
from utils.script_utils import get_file_content
from preup.utils import write_to_file
from preup.xml_manager import html_escape, html_escape_string


class TestXMLCompose(unittest.TestCase):
    def test_compose(self):
        dir_name = "tests/RHEL6_7"
        result_dir = dir_name+variables.result_prefix
        if os.path.exists(result_dir):
            shutil.rmtree(result_dir)
        shutil.copytree(dir_name, result_dir)
        content = get_file_content(os.path.join(os.path.dirname(__file__),
                                                "..",
                                                "utils",
                                                "template.xml"), "r")
        target_tree = ElementTree.fromstring(content)

        settings.autocomplete = False
        target_tree = run_compose(target_tree, result_dir)
        self.assertTrue(target_tree)

        expected_groups = ['dummy', 'dummy_failed',
                           'dummy_fixed', 'dummy_needs_action', 'dummy_needs_inspection', 'dummy_not_applicable',
                           'dummy_pass', 'dummy_preupg']
        generated_group = []
        for group in target_tree.findall(".//" + xccdf.XMLNS + "Group"):
            generated_group.append(group.get('id'))
        self.assertEqual(['xccdf_preupg_group_'+x for x in expected_groups], generated_group)
        shutil.rmtree(result_dir)


class TestXML(unittest.TestCase):
    def setUp(self):
        self.dirname = "tests/RHEL6_7-results/test"
        if os.path.exists(self.dirname):
            shutil.rmtree(self.dirname)
        os.makedirs(self.dirname)
        self.filename = os.path.join(self.dirname, 'test.ini')
        self.rule = []
        self.test_solution = "test_solution.txt"
        self.check_script = "check_script.sh"
        self.loaded_ini = {}
        test_ini = {'content_title': 'Testing content title',
                    'content_description': ' some content description',
                    'author': 'test <test@redhat.com>',
                    'config_file': '/etc/named.conf',
                    'check_script': self.check_script,
                    'solution': self.test_solution,
                    'applies_to': 'test',
                    'requires': 'bash',
                    'binary_req': 'sed'
            }
        self.assertTrue(test_ini)
        self.loaded_ini[self.filename] = []
        self.loaded_ini[self.filename].append(test_ini)
        check_sh = """#!/bin/bash

#END GENERATED SECTION

#This is testing check script
 """
        check_name = os.path.join(self.dirname, self.check_script)
        write_to_file(check_name, "w", check_sh)
        os.chmod(check_name, 0777)

        solution_text = """
A solution text for test suite"
"""
        test_solution_name = os.path.join(self.dirname, self.test_solution)
        write_to_file(test_solution_name, "w", solution_text)
        os.chmod(test_solution_name, 0777)
        self.xml_utils = XmlUtils(self.dirname, self.loaded_ini)
        self.rule = self.xml_utils.prepare_sections()

    def tearDown(self):
        shutil.rmtree(self.dirname)


    def test_group_xml(self):
        """
        Basic test for whole program
        """
        self.assertTrue(self.loaded_ini[self.filename])
        self.assertTrue(self.rule)

    def test_xml_rule_id(self):
        rule_id = filter(lambda x: '<Rule id="xccdf_preupg_rule_test_check_script" selected="true">' in x, self.rule)
        self.assertTrue(rule_id)

    def test_xml_profile_id(self):
        profile = filter(lambda x: '<Profile id="xccdf_preupg_profile_default">' in x, self.rule)
        self.assertTrue(profile)

    def test_xml_rule_title(self):
        rule_title = filter(lambda x: "<title>Testing content title</title>" in x, self.rule)
        self.assertTrue(rule_title)

    def test_xml_config_file(self):
        conf_file = filter(lambda x: "<xhtml:li>/etc/named.conf</xhtml:li>" in x, self.rule)
        self.assertTrue(conf_file)

    def test_xml_fix_text(self):
        fix_text = filter(lambda x: "<fixtext>_test_SOLUTION_MSG_TEXT</fixtext>" in x, self.rule)
        self.assertTrue(fix_text)

    def test_xml_solution_type_text(self):
        self.loaded_ini[self.filename][0]['solution_type'] = "text"
        self.xml_utils = XmlUtils(self.dirname, self.loaded_ini)
        self.rule = self.xml_utils.prepare_sections()
        fix_text = filter(lambda x: "<fixtext>_test_SOLUTION_MSG_TEXT</fixtext>" in x, self.rule)
        self.assertTrue(fix_text)

    def test_xml_solution_type_html(self):
        self.loaded_ini[self.filename][0]['solution_type'] = "html"
        self.xml_utils = XmlUtils(self.dirname, self.loaded_ini)
        self.rule = self.xml_utils.prepare_sections()
        fix_text = filter(lambda x: "<fixtext>_test_SOLUTION_MSG_HTML</fixtext>" in x, self.rule)
        self.assertTrue(fix_text)

    def test_check_script_author(self):
        self.rule = self.xml_utils.prepare_sections()
        lines = get_file_content(os.path.join(self.dirname, self.check_script), "r", method=True)
        author = filter(lambda x: "test <test@redhat.com>" in x, lines)
        self.assertTrue(author)

    def test_xml_check_export_tmp_preupgrade(self):
        self.rule = self.xml_utils.prepare_sections()
        check_export = filter(lambda x: '<check-export export-name="TMP_PREUPGRADE" value-id="xccdf_preupg_value_test_check_script_state_tmp_preupgrade" />' in x, self.rule)
        self.assertTrue(check_export)

    def test_xml_current_directory(self):
        self.rule = self.xml_utils.prepare_sections()
        cur_directory = filter(lambda x: '<check-export export-name="CURRENT_DIRECTORY" value-id="xccdf_preupg_value_test_check_script_state_current_directory" />' in x, self.rule)
        self.assertTrue(cur_directory)

    def test_xml_check_script_reference(self):
        self.rule = self.xml_utils.prepare_sections()
        check_script_reference = filter(lambda x: '<check-content-ref href="check_script.sh" />' in x, self.rule)
        self.assertTrue(check_script_reference)

    def test_values_id(self):
        self.rule = self.xml_utils.prepare_sections()
        value_tmp_preupgrade = filter(lambda x: '<Value id="xccdf_preupg_value_test_check_script_state_tmp_preupgrade" operator="equals" type="string">' in x, self.rule)
        self.assertTrue(value_tmp_preupgrade)
        value_tmp_preupgrade_set = filter(lambda x: '<value>SCENARIO</value>' in x, self.rule)
        self.assertTrue(value_tmp_preupgrade_set)
        value_current_dir = filter(lambda x: '<Value id="xccdf_preupg_value_test_check_script_state_current_directory"' in x, self.rule)
        self.assertTrue(value_current_dir)
        value_current_dir_set = filter(lambda x: '<value>SCENARIO/test</value>' in x, self.rule)
        self.assertTrue(value_current_dir_set)

    def test_check_script_applies_to(self):
        self.rule = self.xml_utils.prepare_sections()
        lines = get_file_content(os.path.join(self.dirname, self.check_script), "r", method=True)
        applies = filter(lambda x: 'check_applies_to "test"' in x, lines)
        self.assertTrue(applies)

    def test_check_script_common(self):
        self.rule = self.xml_utils.prepare_sections()
        lines = get_file_content(os.path.join(self.dirname, self.check_script), "r", method=True)
        common = filter(lambda x: '. /usr/share/preupgrade/common.sh' in x, lines)
        self.assertTrue(common)

    def test_check_script_requires(self):
        self.rule = self.xml_utils.prepare_sections()
        lines = get_file_content(os.path.join(self.dirname, self.check_script), "r", method=True)
        check_rpm_to = filter(lambda x: 'check_rpm_to "bash" "sed"' in x, lines)
        self.assertTrue(check_rpm_to)


class TestMissingTag(unittest.TestCase):
    def setUp(self):
        self.dir_name = "tests/RHEL6_7/missing_tag"
        os.makedirs(self.dir_name)
        self.filename = os.path.join(self.dir_name, 'test.ini')
        self.rule = []
        self.test_solution = "test_solution.sh"
        self.check_script = "check_script.sh"
        self.loaded_ini = {}
        test_ini = {'content_title':'Testing content title',
                     'content_description': 'Some content description',
                 'author':'test <test@redhat.com>',
                 'config_file': '/etc/named.conf',
                 'solution': self.test_solution,
                 'applies_to':'test',
            }
        self.assertTrue(test_ini)
        self.loaded_ini[self.filename]=[]
        self.loaded_ini[self.filename].append(test_ini)

    def tearDown(self):
        shutil.rmtree(self.dir_name)

    def test_missing_check_script(self):
        """
        Basic test for whole program
        """
        solution_text = """
A solution text for test suite"
"""
        write_to_file(os.path.join(self.dir_name, self.test_solution), "w", solution_text)
        self.xml_utils = XmlUtils(self.dir_name, self.loaded_ini)
        self.rule = self.xml_utils.prepare_sections()

    def test_missing_solution_script(self):
        check_sh="""#!/bin/bash

#END GENERATED SECTION

#This is testing check script
 """
        write_to_file(os.path.join(self.dir_name, self.check_script), "w", check_sh)
        self.xml_utils = XmlUtils(self.dir_name, self.loaded_ini)
        self.assertRaises(SystemExit, lambda: list(self.xml_utils.prepare_sections()))


class TestGroupXML(unittest.TestCase):
    def setUp(self):
        self.dir_name = "tests/RHEL6_7-results/test_group"
        os.makedirs(self.dir_name)
        self.filename = os.path.join(self.dir_name, 'group.ini')
        self.rule = []
        self.loaded_ini = {}
        test_ini = {'group_title': 'Testing content title',
            }
        self.assertTrue(test_ini)
        self.loaded_ini[self.filename] = []
        self.loaded_ini[self.filename].append(test_ini)

    def tearDown(self):
        shutil.rmtree(self.dir_name)

    def test_group_ini(self):
        """
        Basic test creation group.xml file
        """
        self.xml_utils = XmlUtils(self.dir_name, self.loaded_ini)
        self.rule = self.xml_utils.prepare_sections()
        group_tag = filter(lambda x: '<Group id="xccdf_preupg_group_test_group" selected="true">' in x, self.rule)
        self.assertTrue(group_tag)
        title_tag = filter(lambda x: '<title>Testing content title</title>' in x, self.rule)
        self.assertTrue(title_tag)


class HTMLEscapeTest(unittest.TestCase):
    def test_basic(self):
        input_char = ['asd', '<qwe>', "this 'is' quoted"]
        output = html_escape(input_char)
        expected_output = ['asd', '&lt;qwe&gt;', 'this &apos;is&apos; quoted']
        self.assertEqual(output, expected_output)

    def test_basic_string(self):
        """ test if single string is escaped well """
        input_char = "asd < > &"
        expected_output = "asd &lt; &gt; &amp;"
        output = html_escape_string(input_char)
        self.assertEqual(output, expected_output)

    def test_all(self):
        input = ['a<', 'b>', "x'x", 'y"', 'z&z']
        output = html_escape(input)
        expected_ouput = ['a&lt;', 'b&gt;', 'x&apos;x', 'y&quot;', 'z&amp;z']
        self.assertEqual(output, expected_ouput)

    def test_amp_expand(self):
        """ Test whether ampersand is not being expanded multiple times """
        input_char = ['asd<>&']
        output = html_escape(input_char)
        expected_output = ['asd&lt;&gt;&amp;']
        self.assertEqual(output, expected_output)


def suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTest(loader.loadTestsFromTestCase(TestGroupXML))
    suite.addTest(loader.loadTestsFromTestCase(TestXML))
    suite.addTest(loader.loadTestsFromTestCase(TestMissingTag))
    suite.addTest(loader.loadTestsFromTestCase(TestXMLCompose))
    suite.addTest(loader.loadTestsFromTestCase(HTMLEscapeTest))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=3).run(suite())