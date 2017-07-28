from __future__ import print_function, unicode_literals
import logging
import re
import os

from preupg.utils import FileHelper
from preupg.xccdf import XccdfHelper
from preupg import settings
from preupg.logger import logger_report, log_message
try:
    from xml.etree import ElementTree
except ImportError:
    from elementtree import ElementTree
from preupg.xmlgen import xml_tags


class ReportHelper(object):

    @staticmethod
    def get_needs_inspection():
        return settings.needs_inspection

    @staticmethod
    def get_needs_action():
        return settings.needs_action


class ReportParser(object):

    """Class manipulates with XML files created by oscap"""

    def __init__(self, report_path):
        self.path = report_path
        self.element_prefix = "{http://checklists.nist.gov/xccdf/1.2}"
        # ElementTree.fromstring can't parse safely unicode string
        content = FileHelper.get_file_content(report_path, 'rb', False, False)
        self.target_tree = ElementTree.fromstring(content)
        self.profile = "Profile"
        self.changed_results = {}
        self.output_data = []

    def filter_children(self, tree, tag):
        return self.get_nodes(tree, tag, prefix='./')

    def has_children(self, tree, tag):
        return len(self.get_nodes(tree, tag, prefix='./')) > 0

    def filter_grandchildren(self, tree, parent_tag, tag):
        return tree.findall('./%s%s/%s%s' % (self.element_prefix,
                                             parent_tag,
                                             self.element_prefix, tag))

    def get_child(self, tree, tag):
        return self.get_node(tree, tag, self.element_prefix, prefix='./')

    @staticmethod
    def get_node(tree, tag, name_space='', prefix=''):
        return tree.find(prefix + name_space + tag)

    def get_nodes_attrib(self, tree, tag, attrib):
        try:
            return self.get_child(tree, tag).attrib[attrib]
        except (KeyError, AttributeError):
            return ''

    def get_nodes(self, tree, tag, prefix=''):
        return tree.findall(prefix + self.element_prefix + tag)

    def get_nodes_text(self, tree, tag):
        try:
            text = self.get_child(tree, tag).text
        except AttributeError:
            pass
        else:
            if text:
                return text.strip()
        return ''

    def reload_xml(self, path):
        """Function updates self.target_tree with the new path"""
        self.path = path
        # ElementTree.fromstring can't parse safely unicode string
        content = FileHelper.get_file_content(self.path, 'rb', False, False)
        if not content:
            return None

        # remove the BEL characters from the loaded string, because
        # this character causes crash of the parsing function of ElementTree
        # when it occurs
        self.target_tree = ElementTree.fromstring(content.replace("\a", ""))

    def get_select_rules(self):
        selected = self.filter_grandchildren(self.target_tree, self.profile, "select")
        return selected

    def get_allowed_selected_rules(self):
        selected = []
        for sel in self.get_select_rules():
            if sel.get('selected') == 'true':
                selected.append(sel)
        return selected

    def get_number_checks(self):
        """Function returns a number of checkswho are really selected"""
        return len(self.get_allowed_selected_rules())

    def _get_all_rules(self):
        return self.get_nodes(self.target_tree, "Rule", prefix=".//")

    def get_name_of_checks(self):
        """Function returns a names of rules"""
        list_names = {}
        rule_nodes = self._get_all_rules()
        for select in self.get_allowed_selected_rules():
            id_ref = select.get('idref', '')
            rule = [x for x in rule_nodes if x.get('id', '') == id_ref]
            list_names[id_ref] = self.get_nodes_text(rule[0], "title")
        return list_names

    def get_all_rule_results(self):
        """Function returns all rule-result in TestResult xml tag"""
        return self.filter_grandchildren(self.target_tree, "TestResult", "rule-result")

    def get_all_results(self):
        """Function return all results"""
        results = []
        for rule in self.get_all_rule_results():
            results.extend(self.get_nodes(rule, "result", prefix='./'))
        return results

    def write_xml(self):
        """Function writes XML document to file"""
        self.target_tree.set('xmlns:xhtml', 'http://www.w3.org/1999/xhtml/')
        # we really must set encoding here! and suppress it in write_to_file
        data = ElementTree.tostring(self.target_tree, "utf-8")
        FileHelper.write_to_file(self.path, 'wb', data, False)
        self.target_tree = ElementTree.parse(self.path).getroot()

    def modify_result_path(self, result_dir, scenario, mode):
        """Function modifies result path in XML file"""
        for values in self.get_nodes(self.target_tree, "Value", prefix='.//'):
            if '_current_dir' not in values.get('id'):
                continue
            for value in self.get_nodes(values, "value"):
                logger_report.debug("Replace '%s' with '%s'", value.text, os.path.join(result_dir, scenario))
                value.text = value.text.replace("SCENARIO", os.path.join(result_dir, scenario))

        self.write_xml()

    def replace_inplace_risk(self, scanning_results=None):
        """Replace result of a module:
        - from FAIL to NEEDS_INSPECTION if the module has SLIGHT or MEDIUM risk
        - from FAIL to NEEDS_ACTION if the module has HIGH risk
        - from FAIL to ERROR if the module has no risk
        - from UNKNOWN to ERROR
        - to ERROR if the module has some risk but the result isn't FAIL
        """
        changed_results = []
        self.remove_empty_check_import()
        for rule_result in self.get_all_rule_results():
            rule_id = rule_result.get("idref")
            result_node = self.get_child(rule_result, "result")
            inplace_risks = XccdfHelper.get_check_import_inplace_risks(
                rule_result)
            if result_node.text != "fail" and inplace_risks:
                # The only result that may have an inplace risk is "fail"
                logger_report.debug(
                    "Module with result '%s' can't have any inplace risks."
                    " Setting the result to 'error'.\n"
                    " - Module: %s\n - Risks found: %s",
                    result_node.text, rule_id, "|".join(inplace_risks))
                result_node.text = "error"
                changed_results.append(rule_id + ":" + result_node.text)
            if result_node.text == "fail":
                if not inplace_risks:
                    result_node.text = "error"
                    log_message("The result of %s module is 'fail' but without"
                                " any risk." % rule_id, level=logging.ERROR)
                    changed_results.append(rule_id + ":" + result_node.text)
                else:
                    risk_level = XccdfHelper.get_inplace_risk(inplace_risks)
                    self.update_result_based_on_risk(result_node, risk_level)
                    changed_results.append(rule_id + ":" + result_node.text)
                    logger_report.debug("Result 'fail' replaced with '%s' for"
                                        " the '%s' rule.", result_node.text,
                                        rule_id)
            if result_node.text == "unknown":
                result_node.text = "error"
                changed_results.append(rule_id + ":" + result_node.text)
                log_message("Detected 'unknown' result of module %s. Setting"
                            " the result to 'error'."
                            % rule_id, level=logging.ERROR)
        if scanning_results:
            scanning_results.update_data(changed_results)

        self.write_xml()

    def remove_empty_check_import(self):
        """Remove stdout or stderr check-import tags whose text is either empty
        or contains nothing but whitespace characters.
        """
        has_std_name = lambda x: x.get("import-name") in ["stdout", "stderr"]
        is_empty = lambda x: x.text is None or x.text.strip() == ""
        for rule in self.get_all_rule_results():
            for check in self.get_nodes(rule, "check"):
                for node in self.get_nodes(check, "check-import"):
                    if has_std_name(node) and is_empty(node):
                        self.remove_node(check, node)

    @staticmethod
    def remove_node(tree, tag):
        return tree.remove(tag)

    @staticmethod
    def update_result_based_on_risk(result_node, risk_level):
        if risk_level == 0:
            result_node.text = ReportHelper.get_needs_inspection()
        if risk_level == 1:
            result_node.text = ReportHelper.get_needs_action()

    def remove_debug_info(self):
        """Function removes debug information from report"""
        re_expr = r'^preupg.log.DEBUG.*'
        for rule in self.get_all_rule_results():
            for check_import in self.filter_grandchildren(rule,
                                                          "check",
                                                          "check-import"):
                if check_import.text is not None:
                    new_check = []
                    for check in check_import.text.split('\n'):
                        matched = re.match(re_expr, check)
                        if not matched:
                            new_check.append(check)
                    check_import.text = '\n'.join(new_check)
        self.write_xml()

    def strip_whitespaces(self):
        """Strip specific whitespace characters from the start and end of
        stderr/stdout of modules.
        """
        check_imports = self.target_tree.getiterator(self.element_prefix +
                                                     "check-import")
        for check_import in check_imports:
            if check_import.get("import-name") not in ["stdout", "stderr"]:
                continue
            txt = check_import.text
            if txt and txt.startswith('\n') and \
                    txt.endswith('\n\n          \n'):
                check_import.text = txt[1:-13]

    @staticmethod
    def write_xccdf_version(file_name, direction=False):
        """
        Function updates XCCDF version because
        of separate HTML generation and our own XSL stylesheet
        """
        namespace_1 = 'http://checklists.nist.gov/xccdf/1.1'
        namespace_2 = 'http://checklists.nist.gov/xccdf/1.2'
        content = FileHelper.get_file_content(file_name, "rb")
        if direction:
            content = re.sub(namespace_2, namespace_1, content)
        else:
            content = re.sub(namespace_1, namespace_2, content)
        FileHelper.write_to_file(file_name, 'wb', content)

    def update_check_description(self):
        logger_report.debug("Update check description")
        for rule in self._get_all_rules():
            for description in self.filter_children(rule, 'description'):
                lines = description.text.split('\n')
                details = 'Details:'
                expected_results = 'Expected results:'
                attr = ' xml:lang="en"'
                tag_exp_results = expected_results[:-1].lower().replace(' ', '-')
                tag_details = details[:-1].lower()
                found = 0
                for index, line in enumerate(lines):
                    if line.strip().startswith(details):
                        found = 1
                        lines[index] = line.replace(details, '<ns0:' + tag_details + attr + '>')
                        continue
                    if line.strip().startswith(expected_results):
                        found = 1
                        lines[index] = line.replace(expected_results,
                                                    '</ns0:' + tag_details + '>\n<ns0:' + tag_exp_results + attr + '>')
                        continue
                if found == 1:
                    lines.append('</ns0:' + tag_exp_results + '>')
                    description.text = '\n'.join(lines)
        self.write_xml()

    def select_rules(self, list_rules):
        """
        Function marks choice a specific rules based on the content generation

        :return:
        """
        for select in self.get_select_rules():
            idref = select.get('idref', None)
            logger_report.debug(select)
            logger_report.debug(idref)
            if idref in list_rules:
                select.set('selected', 'true')
            else:
                select.set('selected', 'false')
        self.write_xml()

    def check_rules(self, list_rules):
        """
        Function checks if rules exists
        :param list_rules:
        :return: List of rules which does not exist
        """
        unknown_rules = []
        for select in list_rules:
            found = [i for i in self.get_select_rules() if select in i.get('idref')]
            if not found:
                unknown_rules.append(select)
        return unknown_rules

    def list_rules(self):
        list_rules = []
        for select in self.get_select_rules():
            idref = select.get('idref', None)
            if idref:
                list_rules.append(idref)
        return list_rules

    def get_path(self):
        """Function return path to report"""
        return self.path

    def add_global_tags(self, result_dir, scenario, mode, devel_mode, dist_native):

        for child in self.get_nodes(self.target_tree, self.profile):
            last_child = child
            for key, val in iter(xml_tags.GLOBAL_DIC_VALUES.items()):
                if key == "tmp_preupgrade":
                    val = result_dir
                elif key == "migrate" or key == "upgrade":
                    if not mode or 'migrate' in mode or 'upgrade' in mode:
                        val = "1"
                    else:
                        val = "0"
                elif key == "report_dir":
                    val = os.path.join(result_dir, scenario)
                elif key == "devel_mode":
                    val = str(devel_mode)
                elif key == "dist_native":
                    if dist_native is None:
                        val = "sign"
                    else:
                        val = dist_native
                logger_report.debug("'%s:%s'", key, val)
                new_child = ElementTree.Element(self.element_prefix + 'Value',
                                                {'id': xml_tags.TAG_VALUE + key,
                                                 'type': 'string'
                                                 })
                sub_child = ElementTree.SubElement(new_child, self.element_prefix + 'value')
                sub_child.text = val
                self.target_tree.insert(self.target_tree._children.index(last_child) + 1,
                                        new_child)
        self.write_xml()
