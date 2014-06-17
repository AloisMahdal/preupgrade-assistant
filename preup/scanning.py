from preup.logger import *
import logging


def compare_data(row):
    """
     Function sorts a data output
    """
    test_cases = {'error': '01',
                  'fail': '02',
                  'needs_action': '03',
                  'needs_inspection': '04',
                  'fixed': '05',
                  'informational': '06',
                  'pass': '07',
                  'notapplicable': '08',
                  'notchecked': '09'}
    try:
        title, rule_id, result = row.split(':')
    except ValueError:
        return '99'
    else:
        try:
            return test_cases[result]
        except KeyError:
            return '99'


def format_rules_to_table(output_data, content):
    """
    Function format output_data to table
    """
    if not output_data:
        #If output_data does not contain anything then do not print nothing
        return
    max_title_length = max(x for x in [len(l.split(':')[0]) for l in output_data]) + 5
    max_result_length = max(x for x in [len(l.split(':')[2]) for l in output_data]) + 2
    log_message(settings.result_text.format(content))
    message = '-' * (max_title_length + max_result_length + 4)
    log_message("%s" % message)
    for data in sorted(output_data, key=compare_data, reverse=True):
        try:
            title, rule_id, result = data.split(':')
        except ValueError:
            # data is not an information about processed test; let's log it as an error
            log_message(data, level=logging.ERROR)
        else:
            log_message("|%s |%s|" % (title.ljust(max_title_length),
                                      result.strip().ljust(max_result_length)))
    log_message("%s" % message)


class ScanProgress(object):
    """
    The class is used for showing progress during the scan check.
    """
    def __init__(self, total_count, debug):
        self.total_count = total_count
        self.current_count = 0
        self.output_data = []
        self.debug = debug
        self.names = {}
        self.list_names = []

    def get_full_name(self, count):
        """
        Function returns full name from dictionary
        """
        try:
            key = self.list_names[count]
        except IndexError as index_error:
            return ''
        return self.names[key]

    def show_progress(self, stdout_data):
        """
         Function shows a progress of assessment
        """
        self.output_data.append(stdout_data.strip())
        self.current_count += 1
        prev_msg = self.get_full_name(self.current_count - 1)
        cur_msg = self.get_full_name(self.current_count)
        if self.debug:
            log_message(stdout_data)
            if self.total_count > self.current_count:
                log_message(cur_msg)
        else:
            cnt_back = 7 + len(prev_msg) + 3
            log_message('%sdone    (%s)' % ('\b' * cnt_back,
                                            prev_msg),
                        new_line=True,
                        log=False)
            if self.total_count > self.current_count:
                log_message('%.3d/%.3d ...running (%s)' % (self.current_count + 1,
                                                           self.total_count,
                                                           cur_msg),
                            new_line=False,
                            log=False)
        log_message(stdout_data.strip(), print_output=0)

    def set_names(self, names):
        """
        Function sets names of each rule
        names has format:
                key= xccdf_preupg_...
                value = "Full description"
        """
        self.names = names
        self.list_names = sorted(names)

    def get_output_data(self):
        """
        Function gets an output data from oscap
        """
        return self.output_data

    def update_data(self, changed_fields):
        """
        Function updates a data
        """
        for index, row in enumerate(self.output_data):
            try:
                title, rule_id, result = row.split(':')
            except ValueError:
                continue
            else:
                result_list = [x for x in changed_fields if rule_id in x]
                if result_list:
                    self.output_data[index] = "%s:%s:%s" % (title,
                                                            rule_id,
                                                            result_list[0].split(':')[1])
