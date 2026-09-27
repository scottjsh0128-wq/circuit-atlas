; Load only in the existing Virtuoso GUI session. No DB writes or evaluation of requests.
load("/home/buet/.circuit-atlas/cadence-export.il")
unless(boundp('caBridgeGeneration) caBridgeGeneration=0)
caBridgeDirectory="/home/buet/.circuit-atlas/mailbox"

procedure(caBridgeTick(generation)
  when(generation == caBridgeGeneration
    errset(
      let((port filename job request result done success)
        port=outfile(strcat(caBridgeDirectory "/ready") "w")
        when(port fprintf(port "ready\n") close(port))
        foreach(filename getDirFiles(caBridgeDirectory)
          when(strlen(filename)==44 && rexMatchp("^req_[0-9a-f]+\\.pending$" filename)
            job=substring(filename 5 32)
            request=strcat(caBridgeDirectory "/" filename)
            result=strcat(caBridgeDirectory "/result_" job ".json")
            done=strcat(caBridgeDirectory "/done_" job)
            success=errset(caExport(result) t)
            ; Result file is closed before the completion marker is written.
            port=outfile(done "w")
            when(port
              fprintf(port "%s\n" if(success then "ok" else "error"))
              close(port)
            )
            deleteFile(request)
          )
        )
      )
      t
    )
    hiRegTimer(sprintf(nil "caBridgeTick(%d)" generation) 10)
  )
)

procedure(caBridgeStart()
  caBridgeGeneration=caBridgeGeneration+1
  caBridgeTick(caBridgeGeneration)
  printf("Circuit Atlas bridge started. Open the schematic to read.\n")
  t
)

procedure(caBridgeStop()
  caBridgeGeneration=caBridgeGeneration+1
  when(isFile(strcat(caBridgeDirectory "/ready"))
    deleteFile(strcat(caBridgeDirectory "/ready"))
  )
  printf("Circuit Atlas bridge stopped.\n")
  t
)

caBridgeStart()
