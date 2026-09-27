; Circuit Atlas v1 - read-only CURRENT schematic cell snapshot.
; Run Check and Save in Virtuoso first. This script never saves/modifies a cell.
; load("/absolute/path/cadence-export.il")
; caExport("/absolute/path/circuit.json")
; Export v2: instance terminals only; symbol internals are opaque.

procedure(caJsonString(out value)
  let((s ch idx)
    s=if(stringp(value) then value else sprintf(nil "%L" value))
    fprintf(out "\"")
    for(idx 1 strlen(s)
      ch=substring(s idx 1)
      cond(
        ((ch == "\"") fprintf(out "\\\""))
        ((ch == "\\") fprintf(out "\\\\"))
        ((ch == "\n") fprintf(out "\\n"))
        ((ch == "\r") fprintf(out "\\r"))
        ((ch == "\t") fprintf(out "\\t"))
        (t fprintf(out "%s" ch))
      )
    )
    fprintf(out "\"")
  )
)

procedure(caNetName(out net)
  if(net then caJsonString(out net~>name) else fprintf(out "null"))
)

procedure(caExport(path)
  let((cv out cellId firstInst firstPin firstProp firstNet firstPort inst term it prop net port)
    cv=geGetEditCellView()
    unless(cv error("Open a schematic editor before caExport.\n"))
    unless(cv~>cellViewType == "schematic"
      error("caExport requires a schematic cellView, not layout/symbol.\n")
    )
    out=outfile(path "w")
    unless(out error("Cannot write output file: %s\n" path))
    cellId=strcat(cv~>libName "/" cv~>cellName "/" cv~>viewName)
    unwindProtect(
      progn(
        fprintf(out "{\n\"schema\":\"circuit-atlas/1\",\"top\":")
        caJsonString(out cellId)
        fprintf(out ",\"source\":{\"type\":\"cadence-ciw\",\"scope\":\"current-cell-only\",\"parameters\":\"raw-instance-properties; no CDF defaults or evaluation\"},\"cells\":[{\"id\":")
        caJsonString(out cellId)
        fprintf(out ",\"name\":") caJsonString(out cv~>cellName)
        fprintf(out ",\"library\":") caJsonString(out cv~>libName)
        fprintf(out ",\"view\":") caJsonString(out cv~>viewName)
        fprintf(out ",\"instances\":[\n")
        firstInst=t
        foreach(inst setof(item cv~>instances !(item~>libName == "basic" && member(item~>cellName list("ipin" "opin" "iopin"))))
          unless(firstInst fprintf(out ",\n")) firstInst=nil
          fprintf(out "{\"id\":") caJsonString(out inst~>name)
          fprintf(out ",\"name\":") caJsonString(out inst~>name)
          fprintf(out ",\"library\":") caJsonString(out inst~>libName)
          fprintf(out ",\"cell\":") caJsonString(out inst~>cellName)
          fprintf(out ",\"view\":") caJsonString(out inst~>viewName)
          fprintf(out ",\"kind\":") caJsonString(out if(inst~>viewName == "symbol" then "symbol" else "generic"))
          fprintf(out ",\"pinSource\":\"instance-terminals\",\"orientation\":") caJsonString(out inst~>orient)
          fprintf(out ",\"sourcePosition\":[%g,%g]" xCoord(inst~>xy) yCoord(inst~>xy))
          fprintf(out ",\"parameters\":{") firstProp=t
          foreach(prop inst~>prop
            unless(firstProp fprintf(out ",")) firstProp=nil
            caJsonString(out prop~>name) fprintf(out ":") caJsonString(out prop~>value)
          )
          fprintf(out "},\"pins\":[") firstPin=t
          ; Do not invent disconnected pins from master-only terminal definitions.
          foreach(it inst~>instTerms
            term=it~>term
            unless(firstPin fprintf(out ",")) firstPin=nil
            fprintf(out "{\"name\":") caJsonString(out term~>name)
            fprintf(out ",\"direction\":") caJsonString(out term~>direction)
            fprintf(out ",\"net\":") caNetName(out if(it then it~>net else nil))
            fprintf(out "}")
          )
          fprintf(out "]}")
        )
        fprintf(out "],\"nets\":[") firstNet=t
        foreach(net cv~>nets
          unless(firstNet fprintf(out ",")) firstNet=nil
          fprintf(out "{\"name\":") caJsonString(out net~>name)
          fprintf(out ",\"global\":%s" if(net~>isGlobal then "true" else "false"))
          when(net~>numBits fprintf(out ",\"numBits\":%d" net~>numBits))
          fprintf(out "}")
        )
        fprintf(out "],\"ports\":[") firstPort=t
        foreach(port cv~>terminals
          unless(firstPort fprintf(out ",")) firstPort=nil
          fprintf(out "{\"name\":") caJsonString(out port~>name)
          fprintf(out ",\"direction\":") caJsonString(out port~>direction)
          fprintf(out ",\"net\":") caNetName(out port~>net)
          fprintf(out "}")
        )
        fprintf(out "]}]}\n")
      )
      close(out)
    )
    printf("Circuit Atlas: exported current cell %s to %s\n" cellId path)
    t
  )
)
