"""Bounded official Entur routing; no guessed timetables or live-traffic claims."""
from datetime import datetime
import json,math,time
from urllib.parse import urlencode
from urllib.request import Request,urlopen,build_opener,HTTPRedirectHandler

GRAPHQL='https://api.entur.io/journey-planner/v3/graphql'
GEOCODER='https://api.entur.io/geocoder/v1/search'
AIRPORTS={
 'AES':('Ålesund lufthavn Vigra',('ålesund','vigra'),'alesund'),
 'HOV':('Ørsta-Volda lufthamn',('ørsta','volda','hovden'),'orsta-volda'),
 'OSL':('Oslo lufthavn Gardermoen',('oslo','gardermoen'),'oslo'),
 'BGO':('Bergen lufthavn Flesland',('bergen','flesland'),'bergen'),
 'SVG':('Stavanger lufthavn Sola',('stavanger','sola'),'stavanger'),
 'HAU':('Haugesund lufthavn Karmøy',('haugesund','karmøy'),'haugesund')}
QUERY="""query($from:Location!,$to:Location!,$at:DateTime!,$modes:Modes!){trip(
from:$from,to:$to,dateTime:$at,arriveBy:true,numTripPatterns:3,searchWindow:360,
modes:$modes){routingErrors{code} tripPatterns{duration expectedStartTime
expectedEndTime legs{mode duration expectedStartTime expectedEndTime
fromPlace{name} toPlace{name} line{publicCode name}}}}}"""
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def coordinates(value):
    if not isinstance(value,dict) or set(value)!={'latitude','longitude'}:raise ValueError('Coordinates unavailable')
    lat,lon=value['latitude'],value['longitude']
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lon)) or not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Coordinates invalid')
    return {'latitude':lat,'longitude':lon}
def distance_km(a,b):
    a,b=coordinates(a),coordinates(b);p1,p2=map(math.radians,(a['latitude'],b['latitude']))
    dp=math.radians(b['latitude']-a['latitude']);dl=math.radians(b['longitude']-a['longitude'])
    return 6371*2*math.asin(min(1,math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2)))

class EnturTransport:
    def __init__(self,*,http=None,clock=time.monotonic):
        self.http=http or self._http;self.clock=clock;self.airports={}
    @staticmethod
    def _http(url,payload=None):
        if not (url==GRAPHQL or url.startswith(GEOCODER+'?')):raise ValueError('Unsupported transport source')
        request=Request(url,data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type':'application/json','Accept':'application/json','ET-Client-Name':'benny-jarvis','User-Agent':'Project-Jarvis/assistant'})
        with build_opener(NoRedirect).open(request,timeout=12) as response:
            raw=response.read(1024*1024+1)
            if len(raw)>1024*1024:raise ValueError('Transport response too large')
            return json.loads(raw)
    def place(self,name):
        if not isinstance(name,str) or not 3<=len(name)<=160 or '://' in name:raise ValueError('Give a specific starting place')
        data=self.http(GEOCODER+'?'+urlencode({'text':name,'size':3,'lang':'en'}));matches=[]
        for feature in data.get('features',[]):
            try:
                xy=feature['geometry']['coordinates'];point=coordinates({'latitude':xy[1],'longitude':xy[0]})
                if not 57<=point['latitude']<=72 or not 3<=point['longitude']<=33:continue
                matches.append({'label':str(feature['properties'].get('label') or name)[:160],'coordinates':point,'source':'Entur Geocoder'})
            except (KeyError,IndexError,TypeError,ValueError):continue
        if not matches:return None
        if any(distance_km(matches[0]['coordinates'],m['coordinates'])>3 for m in matches[1:]):raise ValueError('Starting place is ambiguous; include town/address')
        return matches[0]
    def airport(self,code):
        if code not in AIRPORTS:return None
        cached=self.airports.get(code)
        if cached and self.clock()-cached[0]<86400:return cached[1]
        query,tokens,slug=AIRPORTS[code]
        data=self.http(GEOCODER+'?'+urlencode({'text':query,'size':5,'lang':'en'}));matches=[]
        for feature in data.get('features',[]):
            try:
                props=feature['properties'];label=str(props.get('label') or props.get('name') or '')[:160]
                if not any(word in label.casefold() for word in ('lufthavn','lufthamn','airport')):continue
                score=sum(token in label.casefold() for token in tokens)
                if not score:continue
                xy=feature['geometry']['coordinates'];point=coordinates({'latitude':xy[1],'longitude':xy[0]})
                if not 57<=point['latitude']<=72 or not 3<=point['longitude']<=33:continue
                matches.append((score,{'code':code,'label':label,'coordinates':point,
                    'source':'Entur Geocoder','source_url':GEOCODER,
                    'airport_information_url':'https://www.avinor.no/en/airport/'+slug+'/info/to-and-from-the-airport/'}))
            except (KeyError,IndexError,TypeError,ValueError):continue
        if not matches:return None
        matches.sort(key=lambda v:v[0],reverse=True)
        if len(matches)>1 and matches[0][0]==matches[1][0] and distance_km(matches[0][1]['coordinates'],matches[1][1]['coordinates'])>3:raise ValueError('Airport location ambiguous')
        self.airports[code]=(self.clock(),matches[0][1]);return matches[0][1]
    def route(self,origin,destination,arrive_by,mode):
        if mode not in ('driving','public_transport') or not isinstance(arrive_by,datetime) or arrive_by.tzinfo is None:raise ValueError('Invalid transport request')
        a,b=coordinates(origin),coordinates(destination)
        if not all(57<=v['latitude']<=72 and 3<=v['longitude']<=33 for v in (a,b)):return {'state':'unsupported_region','options':[],'source_url':'https://entur.no/'}
        modes={'accessMode':'foot','egressMode':'foot','directMode':'car' if mode=='driving' else 'foot',
            'transportModes':[] if mode=='driving' else [{'transportMode':v} for v in ('bus','rail','metro','tram','water','coach')]}
        payload={'query':QUERY,'variables':{'from':{'name':'Trip origin','coordinates':a},'to':{'name':'Airport destination','coordinates':b},'at':arrive_by.isoformat(),'modes':modes}}
        data=self.http(GRAPHQL,payload)
        if data.get('errors'):return {'state':'source_error','options':[],'source_url':'https://entur.no/'}
        trip=data.get('data',{}).get('trip')
        if not isinstance(trip,dict):raise ValueError('Transport response unavailable')
        options=[]
        for row in trip.get('tripPatterns',[])[:6]:
            try:
                start=datetime.fromisoformat(row['expectedStartTime']);end=datetime.fromisoformat(row['expectedEndTime'])
                duration=float(row['duration']);legs=row['legs']
                if start.tzinfo is None or end.tzinfo is None or not start<end<=arrive_by or not 0<duration<=86400:continue
                if abs((end-start).total_seconds()-duration)>120:continue
                leg_modes=[leg['mode'] for leg in legs]
                if mode=='driving' and 'car' not in leg_modes:continue
                if mode=='public_transport' and (not any(m in ('bus','rail','metro','tram','water','coach') for m in leg_modes) or any(m in ('air','car','taxi') for m in leg_modes)):continue
                clean_legs=[]
                for leg in legs[:12]:
                    line=leg.get('line') or {}
                    clean_legs.append({'mode':str(leg['mode'])[:25],'from':str(leg.get('fromPlace',{}).get('name') or '')[:120],
                        'to':str(leg.get('toPlace',{}).get('name') or '')[:120],'line':str(line.get('publicCode') or line.get('name') or '')[:80],
                        'start':leg.get('expectedStartTime'),'end':leg.get('expectedEndTime')})
                options.append({'departure':start.isoformat(),'arrival':end.isoformat(),'duration_minutes':round(duration/60),
                    'legs':clean_legs,'basis':'Routing estimate, not live road traffic' if mode=='driving' else 'Returned Entur itinerary for the requested date/window'})
            except (KeyError,TypeError,ValueError):continue
        options.sort(key=lambda v:v['departure'],reverse=True)
        return {'state':'available' if options else 'routing_error' if trip.get('routingErrors') else 'no_options_in_search_window',
            'options':options[:3],'mode':mode,'arrive_by':arrive_by.isoformat(),'search_window_minutes':360,
            'source':'Entur Journey Planner','source_url':'https://entur.no/','checked_at':datetime.now().astimezone().isoformat()}
