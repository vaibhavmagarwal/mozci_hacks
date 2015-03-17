import datetime
import bugsy
import subprocess
import time

def strip_branch(buildername):
    #parse buildername, ignore branch (i.e. merges)
    retVal = buildername
    branches = ['fx-team', 'mozilla-inbound', 'mozilla-central', 'mozilla-aurora', 'try']
    for branch in branches:
        retVal = retVal.replace(branch, '')
    return retVal


def filter_instances(instances, action_mode=False):
    retVal = []
    oldest = datetime.datetime.now()
    oldinstance = {'buildname': ''}
    for instance in instances:
        instance['oldest'] = False

        # NOTE: I am hacking out these specific job types until we have a working system
        if 'talos' in instance['buildname']:
            continue
        if 'b2g' in instance['buildname']:
            continue
        if 'ndroid' in instance['buildname']:
            continue
        if 'mozmill' in instance['buildname']:
            continue
        if 'cppunit' in instance['buildname']:
            continue
        if 'try' in instance['buildname']:
            continue
        if action_mode:
            if 'ASAN' in instance['buildname']:
                continue
            if 'pgo' in instance['buildname']:
                continue
            # too new of a platform
            if 'Yosemite' in instance['buildname']:
                continue
            # just turned off platform
            if 'Mountain' in instance['buildname']:
                continue

        curtime = datetime.datetime.strptime(instance['timestamp'], '%Y-%m-%dT%H:%M:%S')
        if curtime < oldest:
            oldest = curtime
            if oldinstance in retVal:
                retVal.remove(oldinstance)
            oldinstance = instance
            instance['oldest'] = True

        found = False
        if action_mode:
            if curtime >= oldest:
                if strip_branch(instance['buildname']) == strip_branch(oldinstance['buildname']):
                    continue

            for item in retVal:
                if strip_branch(instance['buildname']) == strip_branch(item['buildname']):
                    found = True
                    break

        if not found:
            retVal.append(instance)

    return retVal

def intermittent_opened_count(previous_date, next_date):
    bugzilla = bugsy.Bugsy()
    bugs = bugzilla.search_for\
                .keywords("intermittent-failure")\
                .change_history_fields(['[Bug creation]'])\
                .timeframe(previous_date, next_date)\
                .search()

    for bug in bugs:

        try:
            comments = bug.get_comments()
            comments = [x for x in comments if x.creator == "tbplbot@gmail.com"]
            #skipping the bugs which occur less than 3
            if len(comments) < 3:
                continue
        except:
            print "issue getting comments for bug %s" % bug.id
            comments = []
        instances = []
        for comment in comments:
            bname = ''
            rev = ''
            timestamp = ''
            lines = comment.text.split('\n')
            for line in lines:
                if line.startswith('buildname'):
                    bname = line.split('buildname: ')[1]
                elif line.startswith('revision'):
                    try:
                        rev = line.split('revision: ')[1]
                    except:
                        print "exception splitting bug %s, line on 'revision: ', %s" % (bug.id, line)
                elif line.startswith('start_time'):
                    timestamp = line.split('start_time: ')[1]
                elif line.startswith('submit_timestamp'):
                    timestamp = line.split('submit_timestamp: ')[1]
            if bname and rev and timestamp:
                instances.append({'revision': rev, 'buildname': bname, 'timestamp': timestamp})

        instances = filter_instances(instances)
        if len(instances) < 3:
            continue

        for x in instance:
            if x['timestamp'] == timestamps[0]:
                oldest_instance = x
        cmd = "python trigger.py --rev %s --back-revisions 30 --times 30 --skip 15 --buildername \"%s\"" % (oldest_instance['revision'], oldest_instance['buildname'])

        timestamps = [x['timestamp'] for x in instances]
        timestamps.sort()
        time_to_second = 0
        time_to_last = 0
        if len(timestamps) > 1:
            start = datetime.datetime.strptime(timestamps[0], '%Y-%m-%dT%H:%M:%S')
            next = datetime.datetime.strptime(timestamps[1], '%Y-%m-%dT%H:%M:%S')
            last = datetime.datetime.strptime(timestamps[-1], '%Y-%m-%dT%H:%M:%S')
            time_to_second = (next - start).total_seconds()
            time_to_last = (last - start).total_seconds()
            # skipping if second intermittent > 1 week
            if (time_to_second/(60.0*60*24*7)) > 1.0:
                continue
        print '%s,%s,%s,%s,%s'   % (bug.id, len(instances), int(time_to_second / 60), int(time_to_last / 60), ','.join(timestamps))
#                    thlink = findTHLink(cmd)
#                    print "%s, %s, %s, 0" % (bug.id, cmd, thlink)

    return bugs

def findTHLink(inputcmd):
    cmd = inputcmd.replace('\"', '')
    parts = cmd.split(' ')
    index = parts.index('--buildername')

    cmd = parts[0:index+1]
    cmd.append(' '.join(parts[index+1:]))
    cmd.append('--dry-run')

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr = proc.communicate()[1]

    retVal = ''
    for line in stderr.split('\n'):
        try:
            if line.index('treeherder') > -1:
                retVal = line.split(' ')[-1]
                break
        except ValueError, e:
            pass

        try:
            if line.index("The service is temporarily unavailable. Please try again later") > -1:
                time.sleep(10)
                return findTHLink(inputcmd)
        except ValueError, e:
            pass


    return retVal


tday = datetime.date.today()
previous_day = tday - datetime.timedelta(days=14)
today = str(tday)
previous_day = str(previous_day)
bugs = intermittent_opened_count(previous_day, today)
