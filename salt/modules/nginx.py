# -*- coding: utf-8 -*-
'''
Support for nginx
'''
import urllib2
# Import salt libs
import salt.utils
import salt.utils.decorators as decorators


# Cache the output of running which('nginx') so this module
# doesn't needlessly walk $PATH looking for the same binary
# for nginx over and over and over for each function herein
@decorators.memoize
def __detect_os():
    return salt.utils.which('nginx')


def __virtual__():
    '''
    Only load the module if nginx is installed
    '''
    if __detect_os():
        return 'nginx'
    return False


def version():
    '''
    Return server version from nginx -v

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.version
    '''
    cmd = '{0} -v'.format(__detect_os())
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(': ')
    return ret[-1]


def configtest():
    '''
    test configuration and exit

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.configtest
    '''

    cmd = '{0} -t'.format(__detect_os())
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(': ')
    return ret[-1]


def signal(signal=None):
    '''
    Signals nginx to start, reload, reopen or stop.

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.signal reload
    '''
    valid_signals = ('start', 'reopen', 'stop', 'quit', 'reload')

    if signal not in valid_signals:
        return

    # Make sure you use the right arguments
    if signal == "start":
        arguments = ''
    else:
        arguments = ' -s {0}'.format(signal)
    cmd = __detect_os() + arguments
    out = __salt__['cmd.run_all'](cmd)

    # A non-zero return code means fail
    if out['retcode'] and out['stderr']:
        ret = out['stderr'].strip()
    # 'nginxctl configtest' returns 'Syntax OK' to stderr
    elif out['stderr']:
        ret = out['stderr'].strip()
    elif out['stdout']:
        ret = out['stdout'].strip()
    # No output for something like: nginxctl graceful
    else:
        ret = 'Command: "{0}" completed successfully!'.format(cmd)
    return ret


def status(url="http://127.0.0.1/status"):
    """
    Return the data from an Nginx status page as a dictionary.
    http://wiki.nginx.org/HttpStubStatusModule

    url
        The URL of the status page. Defaults to 'http://127.0.0.1/status'

    CLI Example:

    .. code-block:: bash

        salt '*' nginx.status
    """
    resp = urllib2.urlopen(url)
    status_data = resp.read()
    resp.close()

    lines = status_data.splitlines()
    if not len(lines) == 4:
        return
    # "Active connections: 1 "
    active_connections = lines[0].split()[2]
    # "server accepts handled requests"
    # "  12 12 9 "
    accepted, handled, requests = lines[2].split()
    # "Reading: 0 Writing: 1 Waiting: 0 "
    _, reading, _, writing, _, waiting = lines[3].split()
    return {
        'active connections': int(active_connections),
        'accepted': int(accepted),
        'handled': int(handled),
        'requests': int(requests),
        'reading': int(reading),
        'writing': int(writing),
        'waiting': int(waiting),
    }


def _list_sites(conf_dir):
    '''
        List all the nagios plugins
        
        CLI Example:
        
        .. code-block:: bash
        
        salt '*' nagios.list_plugins
        '''
    site_list = os.listdir(conf_dir)
    ret = []
    for site_file in site_list:
        # Check if execute bit
        stat_f = os.path.join(conf_dir, site_file)
        execute_bit = stat.S_IXUSR & os.stat(stat_f)[stat.ST_MODE]
        if execute_bit:
            ret.append(sitefile)
    return ret

def site(cmd='list', site_name = None):
    """
    Site manager, list avalable sites, enable site or disable sites
    subcommands supported are enable, disable and list
    .. code-block:: bash

            salt '*' nginx.site enable wordpress-site

    """
    
    nginx_conf_dir = "/etc/nginx"
    available_site_path = nginx_conf_dir + "/sites-available/"
    enable_sites_path = nginx_conf_dir + "/sites-enabled/"

    site_list = _list_sites(available_site_path)
    site_orig = available_site_path + site_name
    site_dest = enable_sites_path + site_name

    if cmd == 'list':
        ret = site_list

    elif cmd == 'enable' and site_name is not None:
        if site_name in site_list:
            ret = __salt__['file.symlink'](site_orig, site_dest)
            signal('reload')

    elif cmd == 'disable' and site_name is not None:
        if site_name in site_list:
            ret = __salt__['file.remove'](site_dest)
            signal('reload')
            
    else:
        ret = "Error, syntax error or site name not provided"

    return ret



