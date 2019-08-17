class Device():
    num_block = 1048
    num_page = 256
    mapping_table = None
    device_number = None
    device_pe_cycle = None
    devices = None
    semi_stripe_table = None
    binded_stripe_table = None
    ppc = None
    max_ppc_size = None

    # [page state, logical address, index]
    # 0 free, 1 valid, 2 invalid, 3 parity, 4 semi valid, 5 invalid semi
    physical_space = None

    pe_cycle = None
    free_page_in_block = None
    current_block = 0
    current_page = 255

    # result
    write_count = 0
    parity_count = 0
    erase_count = 0
    result = []

    def __init__(self, device_number, mapping_table, devices=None, semi_stripe_table=None, binded_stripe_table=None,
                 ppc=None, max_ppc_size=None, result=None):
        self.device_number = device_number
        self.mapping_table = mapping_table
        self.devices = devices
        self.semi_stripe_table = semi_stripe_table
        self.binded_stripe_table = binded_stripe_table
        self.ppc = ppc
        self.max_ppc_size = max_ppc_size
        self.result = result

        self.physical_space = [[[0, 0, 0] for i in range(self.num_page)] for j in range(self.num_block)]
        self.pe_cycle = [0 for i in range(self.num_block)]
        self.free_page_in_block = [self.num_page for i in range(self.num_block)]
        self.device_pe_cycle = 0

    def new_write(self, logical_addr, index):
        current_block, current_page = self.get_free_page()
        self.physical_space[current_block][current_page][0] = 4  # set valid semi
        self.physical_space[current_block][current_page][1] = logical_addr  # update address
        self.physical_space[current_block][current_page][2] = index  # update index
        self.free_page_in_block[current_block] -= 1  # free page -1

        # update mapping_table
        physical_addr = (self.device_number * self.num_block * self.num_page) + (
                current_block * self.num_page) + current_page
        self.mapping_table[logical_addr] = physical_addr
        self.result[0] += 1
        self.write_count += 1
        return physical_addr

    def new_parity(self, index):
        current_block, current_page = self.get_free_page()
        self.physical_space[current_block][current_page][0] = 3  # set parity
        self.physical_space[current_block][current_page][2] = index  # update index
        self.free_page_in_block[current_block] -= 1  # free page -1
        physical_addr = (self.device_number * self.num_block * self.num_page) + (
                current_block * self.num_page) + current_page
        self.result[1] += 1
        self.parity_count += 1
        return physical_addr

    def update(self, block, page):
        if self.physical_space[block][page][0] == 4:  # semi valid
            self.physical_space[block][page][0] = 5
        else:
            self.physical_space[block][page][0] = 2
        old_logical_addr = self.physical_space[block][page][1]
        old_index = self.physical_space[block][page][2]
        # self.physical_space[block][page][1] = 0

        current_block, current_page = self.get_free_page()
        self.free_page_in_block[current_block] -= 1  # free page -1
        self.physical_space[current_block][current_page][1] = old_logical_addr
        self.physical_space[current_block][current_page][2] = old_index
        self.physical_space[current_block][current_page][0] = 1
        phy_addr = (self.device_number * self.num_block * self.num_page) + (
                current_block * self.num_page) + current_page
        self.mapping_table[old_logical_addr] = phy_addr
        self.result[0] += 1
        self.write_count += 1
        return phy_addr, old_index

    def update_parity(self, block, page):
        phy_addr = 0
        if self.physical_space[block][page][0] != 3:
            print('Wrong parity address')
        else:
            self.physical_space[block][page][0] = 2
            old_index = self.physical_space[block][page][2]

            current_block, current_page = self.get_free_page()
            self.free_page_in_block[current_block] -= 1  # free page -1
            self.physical_space[current_block][current_page][2] = old_index
            self.physical_space[current_block][current_page][0] = 3
            phy_addr = (self.device_number * self.num_block * self.num_page) + (
                    current_block * self.num_page) + current_page
        self.result[1] += 1
        self.parity_count += 1
        return phy_addr

    def migrate(self, state, logical_addr, index):
        current_block, current_page = self.get_free_page()
        self.physical_space[current_block][current_page][0] = state
        self.physical_space[current_block][current_page][1] = logical_addr
        self.physical_space[current_block][current_page][2] = index
        self.free_page_in_block[current_block] -= 1  # free page -1

        # update mapping_table
        physical_addr = (self.device_number * self.num_block * self.num_page) + (
                current_block * self.num_page) + current_page
        self.mapping_table[logical_addr] = physical_addr
        if state == 3:
            self.result[1] += 1
            self.parity_count += 1
        else:
            self.result[0] += 1
            self.write_count += 1
        return physical_addr

    def get_free_page(self):
        min_pe_cycle = 5000
        if self.current_page == 255:
            for i in range(self.num_block):
                if self.pe_cycle[i] < min_pe_cycle:
                    if self.free_page_in_block[i] > 0:
                        min_pe_cycle = self.pe_cycle[i]
                        self.current_block = i
            for i in range(self.num_page):
                if self.physical_space[self.current_block][i][0] == 0:  # free page
                    self.current_page = i
                    break
        else:
            self.current_page += 1
        return self.current_block, self.current_page

    def is_parity_page(self, physical_addr):
        target_block = int((physical_addr % (self.num_block * self.num_page)) / self.num_page)
        target_page = int((physical_addr % (self.num_block * self.num_page)) % self.num_page)
        if self.physical_space[target_block][target_page][0] == 3:
            return True
        else:
            return False

    def get_state(self, block, page):
        return self.physical_space[block][page][0]

    def get_logical_addr(self, block, page):
        return self.physical_space[block][page][1]

    def get_index(self, block, page):
        return self.physical_space[block][page][2]

    def set_invalid(self, physical_addr):
        block, page = self.physical_to_reallocation(physical_addr)
        if self.physical_space[block][page][0] == 5:
            self.physical_space[block][page][0] = 2

    def set_valid_semi(self, physical_addr):
        block, page = self.physical_to_reallocation(physical_addr)
        if self.physical_space[block][page][0] == 1:
            self.physical_space[block][page][0] = 4

    def is_free(self, reserve_block=False):
        unfreeblock_count = 0
        for i in range(self.num_block):
            if self.free_page_in_block[i] == 0:
                unfreeblock_count += 1
        # print(str(self.device_number) + ': ' + str(unfreeblock_count))
        if unfreeblock_count > 748:
            if self.gc(reserve_block) == False:
                return False
        return True

    '''
    # only gc 1 block
    def gc(self, reserve_block):
        max_invalid = 0
        num_erase_block = 300
        candidate_block = []
        for i in range(self.num_block):
            if i == reserve_block:
                continue
            if self.free_page_in_block[i] == 0:
                current_invalid = 0
                for j in range(self.num_page):
                    if self.physical_space[i][j][0] == 2 or self.physical_space[i][j][0] == 5: #invalid or semi invalid
                        current_invalid += 1
                if current_invalid > max_invalid:
                    candidate_block = i
        if len(candidate_block) != 300:
            return False

        self.lpc(candidate_block)
        self.clean_block(candidate_block)
        return True
    '''

    def gc(self, reserve_block):
        invalid_table = {}
        num_erase_block = 300
        candidate_block = []
        for i in range(self.num_block):
            if i == reserve_block:
                continue
            if self.free_page_in_block[i] == 0:
                current_invalid = 0
                for j in range(self.num_page):
                    if self.physical_space[i][j][0] == 2 or self.physical_space[i][j][0] == 5:  # invalid or semi invalid
                        current_invalid += 1
                if invalid_table.__contains__(current_invalid) == False:
                    invalid_table[current_invalid] = [i]
                else:
                    invalid_table[current_invalid].append(i)

        for i in range((self.num_block + 1), -1, -1):
            if invalid_table.__contains__(i):
                if len(candidate_block) + len(invalid_table[i]) < num_erase_block:
                    candidate_block += invalid_table[i]
                elif len(candidate_block) + len(invalid_table[i]) > num_erase_block:
                    last_block = num_erase_block - len(candidate_block)
                    candidate_block += invalid_table[i][:last_block]
                    break
                else:
                    candidate_block += invalid_table[i]
                    break
        if len(candidate_block) != num_erase_block:
            return False

        self.lpc(candidate_block)
        self.clean_block(candidate_block)
        return True

    def lpc(self, candidate_block):
        for block_number in candidate_block:
            for i in range(self.num_page):
                if self.physical_space[block_number][i][0] == 1:  # valid
                    physical_addr, old_index = self.update(block_number, i)
                    self.binded_stripe_table[old_index][self.device_number] = physical_addr
                    self.result[0] += 1
                    self.write_count += 1
                elif self.physical_space[block_number][i][0] == 3:  # parity
                    physical_addr = self.update_parity(block_number, i)
                    index = self.physical_space[block_number][i][2]
                    if self.semi_stripe_table[index][self.device_number] in self.ppc:
                        ppc_index = self.ppc.index(self.semi_stripe_table[index][self.device_number])
                        self.ppc[ppc_index] = physical_addr
                    self.binded_stripe_table[index][self.device_number] = physical_addr
                    self.semi_stripe_table[index][self.device_number] = physical_addr
                    self.result[1] += 1
                    self.parity_count += 1
                elif self.physical_space[block_number][i][0] == 4:  # valid semi
                    physical_addr, old_index = self.update(block_number, i)
                    current_block, current_page = self.physical_to_reallocation(physical_addr)
                    self.semi_stripe_table[old_index][self.device_number] = physical_addr
                    self.binded_stripe_table[old_index][self.device_number] = physical_addr
                    self.physical_space[current_block][current_page][0] = 4
                    self.result[0] += 1
                    self.write_count += 1
                elif self.physical_space[block_number][i][0] == 5:  # invalid semi
                    index = self.physical_space[block_number][i][2]
                    physical_addr = None
                    parity_device = None
                    for j in range(5):
                        if j != self.device_number:
                            physical_addr = self.semi_stripe_table[index][j]
                            if self.devices[j].is_parity_page(physical_addr) == True:
                                parity_device = j
                                break
                    try:
                        self.ppc.remove(physical_addr)
                    except ValueError:
                        pass
                    current_block, current_page = self.physical_to_reallocation(physical_addr)
                    physical_addr = self.devices[parity_device].update_parity(current_block, current_page)
                    '''
                    if self.is_free(current_block) == True:
                        physical_addr = self.update_parity(current_block, current_page)
                    else:
                        print('Too much valid data')
                        exit()
                    '''
                    # invalid old semi stripe table
                    for j in range(5):
                        if self.semi_stripe_table[index][j] != self.binded_stripe_table[index][j]:
                            self.devices[j].set_invalid(self.semi_stripe_table[index][j])

                    self.binded_stripe_table[index][parity_device] = physical_addr
                    self.semi_stripe_table[index] = list(self.binded_stripe_table[index])
                    for j in range(5):
                        self.devices[j].set_valid_semi(self.semi_stripe_table[index][j])

    def clean_block(self, candidate_block):
        for block_number in candidate_block:
            for i in range(self.num_page):
                self.physical_space[block_number][i][0] = 0
                self.physical_space[block_number][i][1] = 0
                self.physical_space[block_number][i][2] = 0
            self.free_page_in_block[block_number] = self.num_page
            self.pe_cycle[block_number] += 1

            for i in range(self.num_block):
                if self.pe_cycle[i] > self.device_pe_cycle:
                    self.device_pe_cycle = self.pe_cycle[i]
        self.result[2] += len(candidate_block)
        self.erase_count += len(candidate_block)
        print('Device ' + str(self.device_number) + ': ' + str(self.device_pe_cycle))

    def physical_to_reallocation(self, physical_addr):
        block = int((physical_addr % (self.num_block * self.num_page)) / self.num_page)
        page = int((physical_addr % (self.num_block * self.num_page)) % self.num_page)
        return block, page
