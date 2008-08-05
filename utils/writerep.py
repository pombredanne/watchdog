#!/usr/bin/env python
# encoding: utf-8
"""
writerep.py
Write Your Representative
Created by Pradeep Gowda on 2008-04-24.
"""
import sys
import urllib2
from ClientForm import ParseFile, ParseError, ControlNotFoundError
from BeautifulSoup import BeautifulSoup
from StringIO import StringIO

import web
import captchasolver
from settings import db

name_options = dict(prefix=['pre', 'salutation'],
                    lname=['lname', 'last'],
                    fname=['fname', 'first', 'name'],
                    zipcode=['zip', 'zipcode'],
                    zip4=['zip4'],
                    address=['addr1', 'address'],
                    addr2=['addr2', 'address2'],
                    addr3=['addr3'],
                    city=['city'],
                    state=['state'],
                    email=['email'],
                    phone=['phone'],
                    issue=['issue', 'subject', 'topic'],
                    message=['message', 'msg', 'comment', 'text']
                )

def safe(f):
    def g(*args, **kw):
        try:
            return f(*args, **kw)
        except:
            print >> sys.stderr, '%s Failed with %s, %s' % (f.__name__, args, kw)
            return None
    return g        

@safe
def urlopen(url, data=None):
    return urllib2.urlopen(url, data)
    
def first(seq):
    """returns first True element"""    
    if not seq: return False
    for s in seq:
        if s:
            return s
    return None        

PRODUCTION_MODE = False # XXX: read from config?
class Form(object):
    def __init__(self, f):
        self.f = f
        
    def __repr__(self):
        return repr(self.f)
        
    def __str__(self):
        return str(self.f)
                    
    def production_click(self):
        if PRODUCTION_MODE:
            request = self.f.click()
            response = urlopen(request.get_full_url(), request.get_data())
            return 
        else:
            pass
        return True
    
    def click(self):
        return self.f.click()
                    
    def select_value(self, control, options):
        if not isinstance(options, list): options = [options]
        items = [str(item).lstrip('*') for item in control.items]
        for option in options: 
            for item in items:
                if option.lower() in item.lower():
                    return [item]
        return [item]

    def fill_all(self, **d):
        for k, v in d.items():
            self.fill(v, name=k)
                    
    def fill_name(self, prefix, fname, lname):
        self.fill(prefix, 'prefix')
        if self.fill(lname, 'lname'):
            return self.fill(fname, 'fname')
        else:
            name = "%s %s %s" % (prefix, lname, fname)
            return self.fill(fname, 'fname')
    
    def fill_address(self, addr1, addr2, addr3=''):    
        if self.fill(addr2, 'addr2'):
            return self.fill(addr1, 'address')
        else:
            address = "%s %s %s" % (addr1, addr2, addr3)
            return self.fill(address, 'address')

    def fill(self, value, name=None, type=None):
        c = self.find_control(name=name, type=type)
        if c and not c.readonly:
            if c.type in ['select', 'radio']: value = self.select_value(c, value)
            self.f.set_value(value, name=c.name)
            return True 
        return False
    
    def has(self, name=None, type=None):
        return bool(self.find_control(name=name, type=type))
    
    def find_control(self, name=None, type=None):
        """return the form control of type `type` or matching name_options of `name`"""
        if not (name or type): return
        
        try:
            names = name_options[name]
        except KeyError: 
            names = name and [name]
        c = None
        if type: c = self.find_control_by_type(type)
        if not c and names: c = first(self.find_control_by_name(name) for name in names)
        if not c and names: c = first(self.find_control_by_id(name) for name in names)
        return c     

    def find_control_by_name(self, name):
        name = name.lower()
        return first(c for c in self.f.controls if c.name and name in c.name.lower())
        
    def find_control_by_id(self, id):
        id = id.lower()
        return first(c for c in self.f.controls if c.id and id in c.id.lower())
        
    def find_control_by_type(self, type):
        try:
            return self.f.find_control(type=type)
        except ControlNotFoundError:
            return None
                    
            
def has_message(soup, msg):
    bs = soup.findAll('b')
    msg = msg.lower()
    for b in bs:
        errmsg = str(b.string).lower()
        if errmsg.find(msg) > -1:
            return True
    return False

def get_forms(url, data=None):    
    response = urlopen(url, data).read()
    try:
        forms = ParseFile(StringIO(response), url, backwards_compat=False)
    except:
        forms = []
    
    return [Form(f) for f in forms], response

class ZipShared(Exception): pass
class ZipIncorrect(Exception): pass
class ZipNotFound(Exception): pass
class WyrError(Exception): pass
class NoForm(Exception): pass

def writerep_wyr(district, zipcode, state, prefix, fname, lname,
            addr1, city, phone, email, msg, addr2='', addr3='', zip4=''):
          
    def wyr_step1(url):
        forms, response = get_forms(url)
        form = forms[1]
        # state names are in form: "PRPuerto Rico"
        state_options = form.find_control_by_name('state').items
        state_l = [s.name for s in state_options if s.name[:2] == state]
        form.fill_all(state=state_l[0], zip=zipcode, zip4=zip4)
        print 'step1 done',
        request = form.click()
        return request
            
    def get_challenge(soup):
          labels =  filter(lambda x: x.get('for') == 'HIP_response', soup.findAll('label')) 
          if labels: return labels[0].string
          else: return None        
            
    def get_wyr_form2(request):
        url, data = request.get_full_url(), request.get_data() 
        forms, response = get_forms(url, data)
        soup = BeautifulSoup(response)    
        if len(forms) < 2:
            if has_message(soup, "is shared by more than one"): raise ZipShared
            elif has_message(soup, "not correct for the selected State"): raise ZipIncorrect
            elif has_message(soup, "was not found in our database."): raise ZipNotFound
            elif has_message(soup, "Use your web browser's <b>BACK</b> capability "): raise WyrError
            elif forms: return forms[0]   
            else: raise NoForm
        else:
            challenge = get_challenge(soup)
            if challenge:
                form = forms[1]
                try:
                    solution = captchasolver.solve(challenge)
                except Exception, detail:
                    print >> sys.stderr, 'Exception in CaptchaSolve', detail
                    print 'Could not solve:', challenge,
                else:        
                    form.f['HIP_response'] = str(solution)
                    request = form.click()
                    form = get_wyr_form2(request)
                    return form
            else:
                return forms[1]
        
    def wyr_step2(request):
        if not request: return
        form = get_wyr_form2(request)
        if not form: return

        if form.fill_name(prefix, fname, lname):
            form.fill_address(addr1, addr2, addr3)
            form.fill_all(city=city, phone=phone, email=email)
            request = form.click()
            print 'step2 done',
            return request
            
    def wyr_step3(request):
        if not request: return None
        forms, response = get_forms(request.get_full_url(), request.get_data())
        forms = filter(lambda f: f.has(type='textarea'), forms)
        if forms:
            form = forms[0]
            if form.fill(msg, type='textarea'):
                print 'step3 done',
                return form.production_click()
        else:
            print >> sys.stderr, response

    wyr_url = 'https://forms.house.gov/wyr/welcome.shtml'
    return wyr_step3(wyr_step2(wyr_step1(wyr_url)))

def writerep_ima(ima_link, district, zipcode, state, prefix, fname, 
                 lname, addr1, city, phone, email, msg, 
                 addr2='', addr3='', zip4=''):

    forms, response = get_forms(ima_link)
    forms = filter(lambda f: f.has(type='textarea') , forms)
    
    if forms:
        f = forms[0]
        f.fill_name(prefix, fname, lname)
        f.fill_address(addr1, addr2, addr3)
        f.fill_all(city=city, state=state.upper(), zipcode=zipcode, zip4=zip4, email=email, phone=phone, issue=['GEN', 'OTH'])
        f.fill(type='textarea', value=msg)
        return f.production_click()
    else:
        print 'Error: No IMA form in', ima_link,
                     
def has_wyr_form(district):
    wyr_forms = db.select('wyr', what='wyr_form', 
                          where='district = $district and wyr_form IS NOT NULL', 
                          vars=locals())
    if wyr_forms: return True
    return False

def get_ima_link(district):
    contactforms = db.select('wyr', what='contactform', 
                             where='district = $district and imaissue = true', 
                             vars=locals())
    if contactforms: return contactforms[0].contactform
    return None

def get_zipauth_link(district):
    contactforms = db.select('wyr', what='contactform', 
                             where='district = $district and zipauth = true', 
                             vars=locals())
    if contactforms: return contactforms[0].contactform
    return None

def find_form(forms, names):
    names = [name.upper() for name in names]
    fform = None
    for form in forms:
        for c in form.controls:
            for name in names:
                if c.name and (name in c.name.upper()):
                    fform = form
    return fform         
            
def fill(form, names, value):
    """ fills the matching `form` field with `value`"""
    if not isinstance(names, list): names = [names]
    control = matching_control(form, names)
    if control:
        if control.type in ['select', 'radio']: 
            value = select_value(control, value)
        form[control.name] = value
        return True    
    return False
    
def writerep_zipauth(zipauth_link, district, zipcode, state, prefix, fname, 
                     lname, addr1, city, phone, email, msg, 
                     addr2='', addr3='', zip4=''):
            
    def zipauth_step1(f):    
        f.fill_name(prefix, fname, lname)
        f.fill_all(email=email, zipcode=zipcode, zip4=zip4)
        print 'step1 done',
        return f.click()
        
    def zipauth_step2(request):   
        forms, response = get_forms(request.get_full_url(), request.get_data())
        forms = filter(lambda f: f.has(type='textarea'), forms)
        if forms:
            f = forms[0]
            f.fill_name(prefix, fname, lname)
            f.fill_address(addr1, addr2, addr3)
            f.fill_all(city=city, zip=zipcode, email=email, phone=phone, issue=['GEN', 'OTH'])
            f.fill(type='textarea', value=msg)
            print 'step2 done',
            return f.production_click()
        else:
            soup = BeautifulSoup(response)
            if has_message(soup, 'zip code is split between more than one'): raise ZipShared
            
    forms, response = get_forms(zipauth_link)
    forms = filter(lambda f: f.has(name='zip'), forms)
    if forms:
        return zipauth_step2(zipauth_step1(forms[0]))
    else: 
        print 'Error: No zipauth form in', zipauth_link
        return        
    
def writerep(district, zipcode, prefix, fname, lname, 
             addr1, city, phone, email, msg, addr2='', addr3='', zip4=''):
    '''
    Note: zip4 is required for contactforms with `zipauth` flag
    as well as those with multiple representatives for the district
    '''
    state = district[:2]
    prefix = prefix.rstrip('.')
    args = locals();
    
    wyr = has_wyr_form(district)
    ima_link = get_ima_link(district)
    zipauth_link = get_zipauth_link(district)
    msg_sent = False

    if wyr:
        print 'wyr_form',
        msg_sent = writerep_wyr(**args)

    if ima_link and not msg_sent:
        print 'ima_link',
        args['ima_link'] = ima_link
        msg_sent = writerep_ima(**args)
        
    if zipauth_link and not msg_sent:
        print 'zip auth',
        args['zipauth_link'] = zipauth_link
        msg_sent = writerep_zipauth(**args)
    
    return msg_sent

def getdistzipdict(zipdump):
    """returns a dict with district names as keys zipcodes falling in it as values"""
    d = {}
    for line in zipdump.strip().split('\n'):
        zip5, zip4, dist = line.split('\t')
        d[dist] = (zip5, zip4)
    return d

try:        
   dist_zip_dict =  getdistzipdict(file('zip_per_dist.tsv').read())
except:
   import os, sys
   path = os.path.dirname(sys.modules[__name__].__file__)
   dist_zip_dict =  getdistzipdict(file(path + '/zip_per_dist.tsv').read())

def getzip(dist):
    return dist_zip_dict[dist]
    
def test(formtype=None):
    query = "select district from wyr " 
    if formtype == 'wyr':  query += "where wyr_form='t'"
    elif formtype == 'ima': query += "where imaissue='t'"
    elif formtype == 'zipauth': query += "where zipauth='t'"
    
    dists = [r.district for r in db.query(query)]
    for dist in dists:
        print dist,        
        zip5, zip4 = getzip(dist)
        msg_sent = writerep(dist, zipcode=zip5, zip4=zip4, prefix='Mr.', 
                    fname='watchdog', lname ='Tester', addr1='111 av', addr2='addr extn', city='test city', 
                    phone='001-001-001', email='test@watchdog.net', msg='testing...')
        print msg_sent and 'Success' or 'Failure'
    
if __name__ == '__main__':
    test('wyr')
    test('ima')
    test('zipauth')
