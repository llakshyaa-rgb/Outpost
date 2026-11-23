"""Dependency-free static analysis primitives for OUTPOST/CyberDesk."""
from __future__ import annotations
import re, struct

MAGIC = [
    (b"\x7fELF","ELF"),(b"MZ","PE/DOS"),(b"PK\x03\x04","ZIP/APK/Office"),
    (b"%PDF-","PDF"),(b"\x89PNG\r\n\x1a\n","PNG"),(b"\xff\xd8\xff","JPEG"),
    (b"GIF8","GIF"),(b"SQLite format 3","SQLite"),(b"RIFF","RIFF"),
    (b"OggS","OGG"),(b"\xd4\xc3\xb2\xa1","PCAP little-endian"),
    (b"\xa1\xb2\xc3\xd4","PCAP big-endian"),(b"\x0a\x0d\x0d\x0a","PCAPNG"),
]

def strings(raw: bytes, limit: int = 120) -> list[dict]:
    out=[]
    for match in re.finditer(rb"[\x20-\x7e]{5,}", raw[:4_000_000]):
        out.append({"offset":match.start(),"encoding":"ascii","text":match.group().decode("ascii","replace")[:240]})
        if len(out)>=limit: break
    if len(out)<limit:
        for match in re.finditer(rb"(?:[\x20-\x7e]\x00){5,}", raw[:4_000_000]):
            out.append({"offset":match.start(),"encoding":"utf-16le","text":match.group().decode("utf-16le","replace")[:240]})
            if len(out)>=limit: break
    return out

def hexdump(raw: bytes, offset: int = 0, length: int = 1024) -> list[str]:
    if offset < 0 or offset > len(raw): raise ValueError("Offset is outside the file")
    length=max(0,min(int(length),4096))
    rows=[]
    for pos in range(offset,min(len(raw),offset+length),16):
        part=raw[pos:pos+16]
        hx=" ".join(f"{b:02x}" for b in part).ljust(47)
        text="".join(chr(b) if 32<=b<127 else "." for b in part)
        rows.append(f"{pos:08x}  {hx}  |{text}|")
    return rows

def elf_header(raw: bytes) -> dict:
    if len(raw)<52 or raw[:4]!=b"\x7fELF": raise ValueError("Not a valid ELF header")
    cls,encoding=raw[4],raw[5]
    if cls not in (1,2) or encoding not in (1,2): raise ValueError("Unsupported ELF class or byte order")
    endian="<" if encoding==1 else ">"
    if cls==1:
        vals=struct.unpack_from(endian+"HHIIIIIHHHHHH",raw,16)
        entry,phoff,shoff=vals[3],vals[4],vals[5]
    else:
        if len(raw)<64: raise ValueError("Truncated ELF64 header")
        vals=struct.unpack_from(endian+"HHIQQQIHHHHHH",raw,16)
        entry,phoff,shoff=vals[3],vals[4],vals[5]
    machine={3:"x86",40:"ARM",62:"x86-64",183:"AArch64",243:"RISC-V",8:"MIPS"}.get(vals[1],f"machine {vals[1]}")
    return {"format":"ELF","class":32 if cls==1 else 64,"byte_order":"little" if cls==1 and encoding==1 or cls==2 and encoding==1 else "big","type":vals[0],"machine":machine,"entry_point":hex(entry),"program_header_offset":phoff,"section_header_offset":shoff}

def pe_header(raw: bytes) -> dict:
    if len(raw)<64 or raw[:2]!=b"MZ": raise ValueError("Not a PE/MZ file")
    offset=struct.unpack_from("<I",raw,0x3c)[0]
    if offset>len(raw)-24 or raw[offset:offset+4]!=b"PE\x00\x00": raise ValueError("PE signature not found")
    machine,sections,timestamp,symptr,symbols,opt_size,flags=struct.unpack_from("<HHIIIHH",raw,offset+4)
    machine_name={0x14c:"x86",0x8664:"x86-64",0x1c0:"ARM",0xaa64:"ARM64"}.get(machine,f"0x{machine:04x}")
    magic=struct.unpack_from("<H",raw,offset+24)[0] if opt_size>=2 and len(raw)>=offset+26 else 0
    section_rows=[]
    table=offset+24+opt_size
    for index in range(min(sections,96)):
        pos=table+index*40
        if pos+40>len(raw): break
        name=raw[pos:pos+8].split(bytes([0]),1)[0].decode("ascii","replace")
        virtual_size,virtual_address,raw_size,raw_offset=struct.unpack_from("<IIII",raw,pos+8)
        characteristics=struct.unpack_from("<I",raw,pos+36)[0]
        section_rows.append({"name":name,"virtual_size":virtual_size,"virtual_address":hex(virtual_address),"raw_size":raw_size,"raw_offset":raw_offset,"characteristics":hex(characteristics)})
    return {"format":"PE","machine":machine_name,"sections":sections,"section_table":section_rows,"timestamp":timestamp,"optional_header":"PE32+" if magic==0x20b else "PE32" if magic==0x10b else "unknown","characteristics":hex(flags),"header_offset":offset}

def carve(raw: bytes, limit: int = 40) -> list[dict]:
    found=[]
    for magic,label in MAGIC:
        start=0
        while len(found)<limit:
            pos=raw.find(magic,start)
            if pos<0: break
            found.append({"offset":pos,"format":label})
            start=pos+1
    return sorted(found,key=lambda x:x["offset"])[:limit]

def _packet_summary(frame: bytes, link_type: int) -> dict:
    result={"captured_bytes":len(frame)}
    pos=0
    ethertype=None
    if link_type==1 and len(frame)>=14:
        ethertype=struct.unpack_from("!H",frame,12)[0]
        pos=14
        depth=0
        while ethertype in (0x8100,0x88a8) and depth<2 and len(frame)>=pos+4:
            ethertype=struct.unpack_from("!H",frame,pos+2)[0]
            pos+=4
            depth+=1
        result["link"]="Ethernet"
    elif link_type==101:
        result["link"]="Raw IP"
        ethertype=0x0800 if frame and frame[0]>>4==4 else 0x86dd if frame and frame[0]>>4==6 else None
    elif link_type==113 and len(frame)>=16:
        result["link"]="Linux cooked"
        ethertype=struct.unpack_from("!H",frame,14)[0]
        pos=16
    else:
        result["link_type"]=link_type
        return result
    if ethertype==0x0800 and len(frame)>=pos+20:
        ihl=(frame[pos]&15)*4
        if frame[pos]>>4!=4 or ihl<20 or len(frame)<pos+ihl: return result
        proto=frame[pos+9]
        result.update({"network":"IPv4","source":".".join(map(str,frame[pos+12:pos+16])),"destination":".".join(map(str,frame[pos+16:pos+20]))})
        pos+=ihl
    elif ethertype==0x86dd and len(frame)>=pos+40:
        proto=frame[pos+6]
        import ipaddress
        result.update({"network":"IPv6","source":str(ipaddress.IPv6Address(frame[pos+8:pos+24])),"destination":str(ipaddress.IPv6Address(frame[pos+24:pos+40]))})
        pos+=40
    else:
        result["ethertype"]=hex(ethertype) if ethertype is not None else None
        return result
    result["protocol"]={1:"ICMP",2:"IGMP",6:"TCP",17:"UDP",58:"ICMPv6"}.get(proto,f"IP protocol {proto}")
    if proto in (6,17) and len(frame)>=pos+4:
        result["source_port"],result["destination_port"]=struct.unpack_from("!HH",frame,pos)
        if proto==6 and len(frame)>=pos+14: result["tcp_flags"]=hex(frame[pos+13])
    return result


def pcap_summary(raw: bytes) -> dict:
    if raw.startswith(bytes.fromhex("0a0d0d0a")):
        return {"format":"PCAPNG","note":"PCAPNG section header detected. Full block decoding is not enabled in the lightweight core."}
    formats={
        bytes.fromhex("d4c3b2a1"):("<","microseconds"),bytes.fromhex("a1b2c3d4"):(">","microseconds"),
        bytes.fromhex("4d3cb2a1"):("<","nanoseconds"),bytes.fromhex("a1b23c4d"):(">","nanoseconds")}
    if len(raw)<24 or raw[:4] not in formats: raise ValueError("Not a supported classic PCAP capture")
    endian,resolution=formats[raw[:4]]
    major,minor,zone,sig,snap,network=struct.unpack_from(endian+"HHiIII",raw,4)
    pos,packets,truncated=24,0,False
    samples=[]
    while pos+16<=len(raw) and packets<1_000_000:
        sec,fraction,incl,orig=struct.unpack_from(endian+"IIII",raw,pos)
        if incl>snap or incl>len(raw)-pos-16:
            truncated=True
            break
        frame=raw[pos+16:pos+16+incl]
        if len(samples)<100:
            sample=_packet_summary(frame,network)
            sample.update({"number":packets+1,"captured_length":incl,"original_length":orig,"timestamp_seconds":sec,"timestamp_fraction":fraction})
            samples.append(sample)
        pos+=16+incl
        packets+=1
    if pos<len(raw): truncated=True
    return {"format":"PCAP","version":f"{major}.{minor}","timestamp_resolution":resolution,"snaplen":snap,"link_type":network,"packets":packets,"packet_samples":samples,"samples_truncated":packets>len(samples),"truncated_or_trailing_data":truncated}
def analyze(mode: str, raw: bytes, text: str = "") -> dict:
    if len(raw)>20_000_000: raise ValueError("Analysis input exceeds 20 MB")
    if mode=="strings": return {"strings":strings(raw),"total_bytes":len(raw)}
    if mode=="hexdump": return {"hexdump":hexdump(raw),"total_bytes":len(raw)}
    if mode=="carve": return {"embedded_formats":carve(raw),"total_bytes":len(raw)}
    if mode=="elf": return elf_header(raw)
    if mode=="pe": return pe_header(raw)
    if mode=="pcap": return pcap_summary(raw)
    raise ValueError("Unknown CyberDesk analysis mode")
