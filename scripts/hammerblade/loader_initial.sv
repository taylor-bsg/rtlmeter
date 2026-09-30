  localparam num_tiles_lp = `BSG_MACHINE_GLOBAL_X * `BSG_MACHINE_GLOBAL_Y;
  string nbf_file;
  initial begin : load_image
    string count_arg;
    int unsigned iterations;
    int tile;
    bsg_nbf_s entry;
    bit [num_tiles_lp-1:0] patched, released;
    bit terminated, fenced;

    if (!$value$plusargs("iterations=%s", count_arg) || count_arg.len() == 0)
      $fatal(1, "Missing +iterations");
    iterations = 0;
    for (int i = 0; i < count_arg.len(); i++) begin
      if (count_arg.getc(i) < "0" || count_arg.getc(i) > "9")
        $fatal(1, "Invalid +iterations: expected an integer from 1 to 1000000");
      iterations = iterations * 10 + int'(count_arg.getc(i)) - 48;
      if (iterations > 1000000)
        $fatal(1, "Invalid +iterations: expected an integer from 1 to 1000000");
    end
    if (iterations == 0)
      $fatal(1, "Invalid +iterations: expected an integer from 1 to 1000000");
    if (!$value$plusargs("nbf_file=%s", nbf_file))
      $fatal(1, "Missing +nbf_file");
    $readmemh(nbf_file, nbf);

    // The linker reserves byte address 8 (word EPA 2) in each tile's DMEM,
    // after the two interrupt words. Patch the image before the normal loader
    // sends any packets; its credit fence completes these writes before unfreeze.
    patched = '0;
    released = '0;
    terminated = 0;
    fenced = 0;
    for (int i = 0; i < max_nbf_p; i++) begin
      entry = nbf[i];
      if (&entry) begin
        terminated = 1;
        break;
      end
      if (&entry.x_cord && &entry.y_cord && entry.epa == 0 && entry.data == 0) begin
        fenced = 1;
        continue;
      end
      if (int'(entry.x_cord) >= `BSG_MACHINE_ORIGIN_X_CORD
          && int'(entry.x_cord) < `BSG_MACHINE_ORIGIN_X_CORD + `BSG_MACHINE_GLOBAL_X
          && int'(entry.y_cord) >= `BSG_MACHINE_ORIGIN_Y_CORD
          && int'(entry.y_cord) < `BSG_MACHINE_ORIGIN_Y_CORD + `BSG_MACHINE_GLOBAL_Y) begin
        tile = (int'(entry.y_cord) - `BSG_MACHINE_ORIGIN_Y_CORD) * `BSG_MACHINE_GLOBAL_X
               + int'(entry.x_cord) - `BSG_MACHINE_ORIGIN_X_CORD;
        if (entry.epa == 32'h8000 && entry.data == 0) begin
          if (!(&patched) || !fenced || released[tile])
            $fatal(1, "Invalid NBF: tile release before iteration patch/fence or duplicate release");
          released[tile] = 1;
          continue;
        end
        if (entry.epa == 2) begin
          if (patched[tile] || entry.data != 32'h48424954)
            $fatal(1, "Invalid NBF: duplicate or missing iteration marker");
          patched[tile] = 1;
          entry.data = iterations;
          nbf[i] = entry;
        end
      end
      if (|released)
        $fatal(1, "Invalid NBF: memory write after tile release");
      fenced = 0;
    end
    if (!terminated || !(&patched) || !(&released))
      $fatal(1, "Invalid NBF: incomplete iteration patch, tile release, or terminator");
    $display("HammerBlade iterations: %0d (patched %0d tiles)", iterations, num_tiles_lp);
  end
