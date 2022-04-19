import os
import glob
import config


def main():
    print('Starting snippet cleanup!')
    files = glob.glob(config.snippet_dir + '/*')
    for f in files:
        os.remove(f)
        print(f'File \'{f}\' was removed')
    print('Finished snippet cleanup!')


if __name__ == "__main__":
    main()
